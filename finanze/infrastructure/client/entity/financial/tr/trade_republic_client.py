import asyncio
import base64
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Optional

import httpx
from aiocache import cached
from dateutil.tz import tzlocal
from tzlocal import get_localzone

from domain.entity_login import (
    EntityLoginResult,
    EntitySession,
    LoginConfirmationType,
    LoginOptions,
    LoginResultCode,
)
from infrastructure.client.entity.financial.tr.api import TradeRepublicApi
from infrastructure.client.entity.financial.tr.portfolio import Portfolio
from infrastructure.client.entity.financial.tr.tr_details import TRDetails
from infrastructure.client.entity.financial.tr.tr_timeline import TRTimeline


def _json_cookie_jar(jar: httpx.Cookies) -> list[dict]:
    simple_cookies: list[dict] = []
    for cookie in jar.jar:
        expires_timestamp = 0
        if cookie.expires is not None:
            try:
                expires_timestamp = int(cookie.expires)
            except ValueError, TypeError:
                expires_timestamp = 0

        cookie_dict = {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "expires": expires_timestamp,
            "secure": cookie.secure,
        }
        simple_cookies.append(cookie_dict)

    return simple_cookies


def _rebuild_cookie_jar(cookie_list: list[dict]) -> httpx.Cookies:
    cookies = httpx.Cookies()

    for cookie_dict in cookie_list:
        if not all(k in cookie_dict for k in ("name", "value", "domain")):
            continue

        name = cookie_dict["name"]
        value = cookie_dict["value"]
        domain = cookie_dict["domain"]
        path = cookie_dict.get("path") or "/"

        cookies.set(
            name,
            value,
            domain=domain,
            path=path,
        )

    return cookies


class TradeRepublicClient:
    IN_APP_POLL_INTERVAL = 3
    _V2_HEADERS = {
        "x-tr-platform": "web",
        "x-tr-app-version": "15.7.0",
    }

    def __init__(self, use_v2: bool = False):
        self._tr_api = None
        self._log = logging.getLogger(__name__)
        self._use_v2 = use_v2
        self._cancel_event: asyncio.Event = asyncio.Event()
        self._stable_device_id: str | None = None

    @staticmethod
    def _generate_stable_device_id() -> str:
        return hashlib.sha512(os.urandom(64)).hexdigest()

    def _build_device_info_header(self) -> str:
        now = datetime.now(tzlocal())
        utc_offset_minutes = int(now.utcoffset().total_seconds() // 60)
        device_info = {
            "stableDeviceId": self._stable_device_id,
            "model": "Apple Macintosh",
            "browser": "Firefox",
            "browserVersion": "138.0",
            "os": "Mac OS",
            "osVersion": "10.15",
            "timezone": self._get_timezone(),
            "timezoneOffset": -utc_offset_minutes,
            "screen": "2560x1440x24",
            "preferredLanguages": ["en-US", "en"],
            "numberOfCores": 4,
        }
        return base64.b64encode(
            json.dumps(device_info, separators=(",", ":")).encode()
        ).decode()

    @staticmethod
    def _get_timezone() -> str:
        try:
            import js

            return str(js.Intl.DateTimeFormat().resolvedOptions().timeZone)
        except Exception:
            return str(get_localzone())

    def _get_v2_headers(self) -> dict:
        return {
            **self._V2_HEADERS,
            "x-tr-device-info": self._build_device_info_header(),
        }

    async def login(
        self,
        phone: str,
        pin: str,
        login_options: LoginOptions,
        process_id: str = None,
        code: str = None,
        waf_token: str = None,
        session: Optional[EntitySession] = None,
    ) -> EntityLoginResult:
        if not phone.startswith("+"):
            return EntityLoginResult(
                LoginResultCode.INVALID_CREDENTIALS,
                message="Phone number must start with international prefix (like +34)",
            )

        self._tr_api = TradeRepublicApi(
            phone_no=phone,
            pin=pin,
            locale="en",
        )

        if session and not login_options.force_new_session:
            self._inject_session(session)
            if await self._resumable_session():
                self._log.debug("Resuming session")
                return EntityLoginResult(LoginResultCode.RESUMED)

        if waf_token:
            self._tr_api._websession.headers["x-aws-waf-token"] = waf_token
        else:
            return EntityLoginResult(
                LoginResultCode.MANUAL_LOGIN,
                details={"phone": phone, "password": pin},
            )

        if not self._stable_device_id:
            self._stable_device_id = self._generate_stable_device_id()

        if code and process_id:
            self._tr_api._process_id = process_id
            try:
                await self._tr_api.complete_weblogin(code)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
                elif e.response.status_code == 400:
                    return EntityLoginResult(LoginResultCode.INVALID_CODE)
                elif e.response.status_code == 403:
                    return EntityLoginResult(LoginResultCode.CURRENTLY_UNAVAILABLE)
                else:
                    self._log.error("Unexpected error during login", exc_info=e)
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR,
                        message=f"Got unexpected error {e.response.status_code} during login",
                    )

            sess_created_at = datetime.now(tzlocal())
            session_payload = self._export_session(waf_token)
            new_session = EntitySession(
                creation=sess_created_at, expiration=None, payload=session_payload
            )
            return EntityLoginResult(LoginResultCode.CREATED, session=new_session)

        elif not code or not process_id:
            if not login_options.avoid_new_login:
                if self._use_v2:
                    return await self._login_v2()
                else:
                    return await self._login_v1()
            else:
                return EntityLoginResult(LoginResultCode.NOT_LOGGED)

        return EntityLoginResult(
            LoginResultCode.UNEXPECTED_ERROR,
            message="Unexpected behavior during login",
        )

    async def _login_v1(self) -> EntityLoginResult:
        try:
            result = await self._initiate_weblogin()
            if isinstance(result, EntityLoginResult):
                return result
            else:
                countdown = result

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 405):
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Invalid challenge token",
                )
            else:
                self._log.error("Unexpected error during login", exc_info=e)
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected error {e.response.status_code} during login, {e.response.text}",
            )

        except ValueError as e:
            if str(e) == "NUMBER_INVALID":
                return EntityLoginResult(
                    LoginResultCode.INVALID_CREDENTIALS,
                    message="Invalid phone number, maybe missing international prefix",
                )
            raise

        process_id = self._tr_api._process_id
        return EntityLoginResult(
            LoginResultCode.CODE_REQUESTED,
            process_id=process_id,
            details={"wait": countdown},
        )

    async def _login_v2(self) -> EntityLoginResult:
        try:
            result = await self._initiate_weblogin_v2()
            if isinstance(result, EntityLoginResult):
                return result
            else:
                process_id = result

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 405):
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Invalid challenge token",
                )
            else:
                self._log.error("Unexpected error during login", exc_info=e)
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected error {e.response.status_code} during login, {e.response.text}",
            )

        except ValueError as e:
            if str(e) == "NUMBER_INVALID":
                return EntityLoginResult(
                    LoginResultCode.INVALID_CREDENTIALS,
                    message="Invalid phone number, maybe missing international prefix",
                )
            raise

        return EntityLoginResult(
            LoginResultCode.CODE_REQUESTED,
            confirmation_type=LoginConfirmationType.IN_APP,
            process_id=process_id,
        )

    def cancel_login(self) -> None:
        self._cancel_event.set()

    async def complete_login(
        self, process_id: str, waf_token: str
    ) -> EntityLoginResult:
        if not self._tr_api:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="No login in progress",
            )

        if not self._stable_device_id:
            self._stable_device_id = self._generate_stable_device_id()

        self._cancel_event.clear()
        result = await self._poll_weblogin_v2(process_id)
        if result is not None:
            return result

        self._tr_api._weblogin = True
        sess_created_at = datetime.now(tzlocal())
        session_payload = self._export_session(waf_token)
        new_session = EntitySession(
            creation=sess_created_at, expiration=None, payload=session_payload
        )
        return EntityLoginResult(LoginResultCode.CREATED, session=new_session)

    async def _resumable_session(self) -> bool:
        try:
            await self._tr_api.settings()
        except httpx.HTTPStatusError:
            self._tr_api._weblogin = False
            return False
        else:
            return True

    async def _initiate_weblogin(self) -> int | EntityLoginResult:
        r = await self._tr_api._websession.post(
            f"{self._tr_api._host}/api/v1/auth/web/login",
            json={"phoneNumber": self._tr_api.phone_no, "pin": self._tr_api.pin},
        )

        j = await r.json()

        errs = j.get("errors")
        err = {}
        if errs:
            err = errs[0]
        try:
            if (
                r.status == 429
                or errs
                and err
                and err.get("errorCode") == "TOO_MANY_REQUESTS"
            ):
                next_attempt_secs = err.get("meta", {}).get("nextAttemptInSeconds", 60)
                details = {
                    "wait": next_attempt_secs,
                }
                return EntityLoginResult(
                    LoginResultCode.COOLDOWN,
                    message=f"Too many attempts, wait {next_attempt_secs} seconds before retrying",
                    details=details,
                )

            elif errs and err and err.get("errorCode"):
                r.raise_for_status()
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Got a unexpected error during login, {err.get('errorMessage')}",
                )

            self._tr_api._process_id = j["processId"]

        except KeyError:
            r.raise_for_status()
            if errs:
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Got a unexpected error during login, {errs}",
                )
            else:
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="processId not in response",
                )

        r.raise_for_status()
        return int(j.get("countdownInSeconds", 0)) + 1

    async def _initiate_weblogin_v2(self) -> str | EntityLoginResult:
        r = await self._tr_api._websession.post(
            f"{self._tr_api._host}/api/v2/auth/web/login",
            json={"phoneNumber": self._tr_api.phone_no, "pin": self._tr_api.pin},
            headers=self._get_v2_headers(),
        )

        j = await r.json()

        errs = j.get("errors")
        err = {}
        if errs:
            err = errs[0]
        try:
            if (
                r.status == 429
                or errs
                and err
                and err.get("errorCode") == "TOO_MANY_REQUESTS"
            ):
                next_attempt_secs = err.get("meta", {}).get("nextAttemptInSeconds", 60)
                details = {
                    "wait": next_attempt_secs,
                }
                return EntityLoginResult(
                    LoginResultCode.COOLDOWN,
                    message=f"Too many attempts, wait {next_attempt_secs} seconds before retrying",
                    details=details,
                )

            elif errs and err and err.get("errorCode"):
                r.raise_for_status()
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Got a unexpected error during login, {err.get('errorMessage')}",
                )

            self._tr_api._process_id = j["processId"]

        except KeyError:
            r.raise_for_status()
            if errs:
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Got a unexpected error during login, {errs}",
                )
            else:
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="processId not in response",
                )

        r.raise_for_status()
        return self._tr_api._process_id

    async def _poll_weblogin_v2(self, process_id: str) -> EntityLoginResult | None:
        expires_at = None
        while True:
            try:
                r = await self._tr_api._websession.get(
                    f"{self._tr_api._host}/api/v2/auth/web/login/processes/{process_id}",
                    headers=self._get_v2_headers(),
                )
                r.raise_for_status()
                j = await r.json()

                status = j.get("status", "").upper()
                if status == "CONFIRMED":
                    self._log.info("TR in-app confirmation succeeded")
                    return None

                if expires_at is None:
                    raw_expires = j.get("expiresAt")
                    if raw_expires:
                        expires_at = datetime.fromisoformat(raw_expires)

                if expires_at and datetime.now(expires_at.tzinfo) >= expires_at:
                    break

                self._log.debug("TR in-app confirmation pending")
            except httpx.HTTPStatusError as e:
                self._log.error("Error polling TR login status", exc_info=e)
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Error checking login status: {e.response.status_code}",
                )

            await asyncio.sleep(self.IN_APP_POLL_INTERVAL)
            if self._cancel_event.is_set():
                self._log.info("TR in-app confirmation cancelled by user")
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Login cancelled by user.",
                )

        self._log.warning("TR in-app confirmation timed out")
        return EntityLoginResult(
            LoginResultCode.UNEXPECTED_ERROR,
            message="In-app confirmation timed out. Please try again.",
        )

    def _export_session(self, waf_token: str) -> dict:
        return {
            "cookies": _json_cookie_jar(self._tr_api._websession.cookies),
            "waf_token": waf_token,
            "stable_device_id": self._stable_device_id,
        }

    def _inject_session(self, session: EntitySession):
        cookies = _rebuild_cookie_jar(session.payload["cookies"])
        self._tr_api._websession.clear_cookies()
        for cookie in cookies.jar:
            self._tr_api._websession.set_cookie(cookie)
        waf_token = session.payload.get("waf_token")
        if waf_token:
            self._tr_api._websession.headers["x-aws-waf-token"] = waf_token
        stable_id = session.payload.get("stable_device_id")
        if stable_id:
            self._stable_device_id = stable_id
        self._tr_api._weblogin = True

    async def close(self):
        if self._tr_api and self._tr_api._ws:
            await self._tr_api._ws.close()

    @cached(ttl=120, noself=True)
    async def get_portfolio(self):
        portfolio = Portfolio(self._tr_api)
        await portfolio.portfolio_loop()
        return portfolio

    async def get_details(
        self,
        isin: str,
        types: Optional[list] = None,
    ):
        if types is None:
            types = ["stockDetails", "mutualFundDetails", "instrument"]
        details = TRDetails(self._tr_api, isin)
        await details.fetch(types)
        return details

    async def get_transactions(
        self,
        since: Optional[datetime] = None,
        already_registered_ids: set[str] = None,
    ):
        dl = TRTimeline(
            self._tr_api,
            since=since,
            requested_data=["timelineTransactions", "timelineDetailV2"],
            already_registered_ids=already_registered_ids,
        )
        return await dl.fetch()

    async def get_user_info(self):
        return await self._tr_api.settings()

    async def get_interest_payouts(self, number_of_payouts: int):
        r = await self._tr_api._web_request(
            f"/api/v1/banking/consumer/interest/payouts?numberOfPayouts={number_of_payouts}"
        )
        r.raise_for_status()
        return await r.json()

    async def get_active_interest_rate(self, account_number: str):
        r = await self._tr_api._web_request(
            f"/api/v1/banking/consumer/interest/{account_number}/rate"
        )
        r.raise_for_status()
        return await r.json()

    async def get_interest_payout_summary(
        self, decimal_separator: str = ",", grouping_separator: str = "."
    ):
        r = await self._tr_api._web_request(
            f"/api/v1/interest/details-screen?decimalSeparator={decimal_separator}&groupingSeparator={grouping_separator}"
        )
        r.raise_for_status()
        return await r.json()

    async def get_portfolio_by_type(self, securities_account_num: Optional[str] = None):
        request = {"type": "compactPortfolioByType"}
        if securities_account_num:
            request["secAccNo"] = securities_account_num
        await self._tr_api.subscribe(request)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    async def get_saving_plans(
        self, securities_account_num: Optional[str] = None
    ) -> dict:
        request = {"type": "savingsPlans"}
        if securities_account_num:
            request["secAccNo"] = securities_account_num
        await self._tr_api.subscribe(request)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    async def get_private_markets_portfolio_status(self) -> dict:
        await self._tr_api.subscribe({"type": "privateMarketsPortfolioStatus"})
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    async def get_private_markets_orders(
        self, securities_account_num: Optional[str] = None
    ) -> dict:
        request = {"type": "privateMarketsOrders"}
        if securities_account_num:
            request["secAccNo"] = securities_account_num
        await self._tr_api.subscribe(request)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    async def get_private_markets_portfolio(self, securities_account_num: str) -> dict:
        request = {
            "type": "privateMarketsPositions",
            "secAccNo": securities_account_num,
        }
        await self._tr_api.subscribe(request)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    @cached(ttl=60, noself=True)
    async def get_instrument_details(self, isin: str) -> dict:
        await self._tr_api.instrument_details(isin)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    @cached(ttl=60, noself=True)
    async def get_stock_details(self, isin: str) -> dict:
        await self._tr_api.stock_details(isin)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    async def ticker(self, isin, exchange):
        await self._tr_api.ticker(isin, exchange=exchange)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    @cached(ttl=43200, noself=True)
    async def get_fund_details(self, isin):
        await self._tr_api.subscribe({"type": "mutualFundDetails", "id": isin})
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response
