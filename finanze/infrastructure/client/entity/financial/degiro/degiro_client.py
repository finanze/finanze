import asyncio
import logging
from datetime import date, datetime

from dateutil.tz import tzlocal
from degiro_connector.core.exceptions import DeGiroConnectionError
from degiro_connector.core.models.model_connection import ModelConnection
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.account import (
    OverviewRequest,
    UpdateOption,
    UpdateRequest,
)
from degiro_connector.trading.models.credentials import Credentials
from degiro_connector.trading.models.transaction import HistoryRequest

from domain.entity_login import (
    EntityLoginResult,
    EntitySession,
    LoginResultCode,
)


class DegiroClient:
    TRADING_TIMEOUT = 1800
    IN_APP_POLL_INTERVAL = 5
    IN_APP_MAX_ATTEMPTS = 24  # 2 minutes max wait

    def __init__(self) -> None:
        self._trading_api: TradingAPI | None = None
        self._log = logging.getLogger(__name__)
        self._cancel_event: asyncio.Event = asyncio.Event()

    async def login(
        self,
        username: str,
        password: str,
        totp_secret: str | None = None,
        one_time_password: int | None = None,
    ) -> EntityLoginResult:
        credentials = Credentials(
            username=username,
            password=password,
            totp_secret_key=totp_secret,
            one_time_password=one_time_password,
        )
        self._trading_api = TradingAPI(credentials=credentials, preload=False)

        try:
            await asyncio.to_thread(self._trading_api.connect)
        except DeGiroConnectionError as e:
            status = e.error_details.status if e.error_details else None
            if status == 12:
                in_app_token = e.error_details.in_app_token if e.error_details else None
                if in_app_token:
                    self._log.info("Degiro in-app confirmation required")
                    return EntityLoginResult(
                        LoginResultCode.CODE_REQUESTED,
                        process_id=in_app_token,
                        details={"confirmation_type": "IN_APP"},
                    )
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="In-app confirmation required but no token received",
                )
            self._log.error("Degiro login failed", exc_info=e)
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
        except Exception as e:
            self._log.error("Unexpected error during Degiro login", exc_info=e)
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=str(e),
            )

        return await self._finalize_login()

    async def complete_login(self, in_app_token: str) -> EntityLoginResult:
        if not self._trading_api:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="No login in progress",
            )

        self._trading_api.credentials.in_app_token = in_app_token
        self._cancel_event.clear()

        for attempt in range(self.IN_APP_MAX_ATTEMPTS):
            try:
                await asyncio.to_thread(self._trading_api.connect)
                self._log.info(
                    "Degiro in-app confirmation succeeded on attempt %d",
                    attempt + 1,
                )
                return await self._finalize_login()
            except DeGiroConnectionError as e:
                status = e.error_details.status if e.error_details else None
                if status == 3:
                    self._log.debug(
                        "Degiro in-app confirmation pending (attempt %d/%d)",
                        attempt + 1,
                        self.IN_APP_MAX_ATTEMPTS,
                    )
                    try:
                        await asyncio.wait_for(
                            self._cancel_event.wait(),
                            timeout=self.IN_APP_POLL_INTERVAL,
                        )
                        self._log.info("Degiro in-app confirmation cancelled by user")
                        return EntityLoginResult(
                            LoginResultCode.UNEXPECTED_ERROR,
                            message="Login cancelled by user.",
                        )
                    except TimeoutError:
                        pass
                    continue
                self._log.error("Degiro in-app login failed", exc_info=e)
                return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
            except Exception as e:
                self._log.error(
                    "Unexpected error during Degiro in-app login", exc_info=e
                )
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=str(e),
                )

        self._log.warning("Degiro in-app confirmation timed out")
        return EntityLoginResult(
            LoginResultCode.UNEXPECTED_ERROR,
            message="In-app confirmation timed out. Please try again.",
        )

    def cancel_login(self) -> None:
        self._cancel_event.set()

    async def _finalize_login(self) -> EntityLoginResult:
        try:
            client_details = await asyncio.to_thread(
                self._trading_api.get_client_details
            )
            if client_details:
                int_account = client_details.get("data", {}).get("intAccount")
                if int_account:
                    self._trading_api.credentials.int_account = int_account
        except Exception as e:
            self._log.warning("Could not fetch client details: %s", e)

        session_payload = self._export_session()
        session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload=session_payload,
        )
        return EntityLoginResult(LoginResultCode.CREATED, session=session)

    def restore_session(self, session: EntitySession) -> bool:
        payload = session.payload
        session_id = payload.get("session_id")
        int_account = payload.get("int_account")
        username = payload.get("username", "")
        password = payload.get("password", "")

        if not session_id:
            return False

        credentials = Credentials(
            username=username,
            password=password,
            int_account=int_account,
        )
        connection_storage = ModelConnection(timeout=self.TRADING_TIMEOUT)
        connection_storage.session_id = session_id

        self._trading_api = TradingAPI(
            credentials=credentials,
            connection_storage=connection_storage,
            preload=False,
        )
        return True

    async def get_portfolio(self) -> dict | None:
        return await asyncio.to_thread(
            self._trading_api.get_update,
            request_list=[
                UpdateRequest(option=UpdateOption.PORTFOLIO, last_updated=0),
            ],
            raw=True,
        )

    async def get_total_portfolio(self) -> dict | None:
        return await asyncio.to_thread(
            self._trading_api.get_update,
            request_list=[
                UpdateRequest(option=UpdateOption.TOTAL_PORTFOLIO, last_updated=0),
                UpdateRequest(option=UpdateOption.CASH_FUNDS, last_updated=0),
            ],
            raw=True,
        )

    async def get_products_info(self, product_ids: list[int]) -> dict | None:
        if not product_ids:
            return {}
        result = await asyncio.to_thread(
            self._trading_api.get_products_info,
            product_list=product_ids,
            raw=True,
        )
        return result if result else {}

    async def get_transactions_history(
        self, from_date: date, to_date: date
    ) -> list[dict]:
        request = HistoryRequest(from_date=from_date, to_date=to_date)
        result = await asyncio.to_thread(
            self._trading_api.get_transactions_history,
            transaction_request=request,
            raw=True,
        )
        if not result:
            return []
        return result.get("data", [])

    async def get_account_overview(self, from_date: date, to_date: date) -> list[dict]:
        request = OverviewRequest(from_date=from_date, to_date=to_date)
        result = await asyncio.to_thread(
            self._trading_api.get_account_overview,
            overview_request=request,
            raw=True,
        )
        if not result:
            return []
        return result.get("cashMovements", [])

    def _export_session(self) -> dict:
        session_id = None
        try:
            session_id = self._trading_api.connection_storage.session_id
        except (ConnectionError, TimeoutError):
            pass

        return {
            "session_id": session_id,
            "int_account": (
                self._trading_api.credentials.int_account
                if self._trading_api.credentials
                else None
            ),
            "username": (
                self._trading_api.credentials.username
                if self._trading_api.credentials
                else ""
            ),
            "password": (
                self._trading_api.credentials.password
                if self._trading_api.credentials
                else ""
            ),
        }
