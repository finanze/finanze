import logging
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from aiocache import cached, Cache
from dateutil.tz import tzlocal

from domain.entity_login import (
    EntityLoginResult,
    EntitySession,
    LoginOptions,
    LoginResultCode,
)
from domain.native_entity import EntityCredentials
from infrastructure.client.http.http_session import new_impersonated_http_session

SESSION_LIFETIME = 4 * 60  # 4 minutes
SCA_STATUS_TIMEOUT = 30

DATE_FORMAT = "%d/%m/%Y"
DASHED_DATE_FORMAT = "%Y-%m-%d"


class INGAPIClient:
    GENOMA_BASE_URL = "https://ing.ingdirect.es/genoma_api/rest"
    GENOMA_LOGIN_BASE_URL = "https://ing.ingdirect.es/genoma_login/rest"
    API_BASE_URL = "https://api.ing.ingdirect.es"

    def __init__(self):
        self._genoma_session = None
        self._genoma_login_session = None
        self._api_session = None
        self._session_expiration = None

        self._log = logging.getLogger(__name__)

    async def _execute_request(
        self,
        path: str,
        method: str,
        body: Optional[dict] = None,
        params: Optional[dict] = None,
        api: bool = True,
        headers: Optional[dict] = None,
    ) -> dict:
        base_url = self.API_BASE_URL if api else self.GENOMA_BASE_URL
        session = self._api_session if api else self._genoma_session
        return await self._send(
            session, method, base_url + path, body=body, params=params, headers=headers
        )

    async def _send(
        self,
        session,
        method: str,
        url: str,
        body: Optional[dict] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> dict:
        response = await session.request(
            method, url, json=body, params=params, headers=headers, **kwargs
        )

        if response.ok:
            return await response.json()

        body_text = await response.text()
        self._log.error("Error Response Body:" + body_text)
        response.raise_for_status()
        return {}

    async def _get_request(
        self, path: str, params: dict = None, api: bool = True
    ) -> dict:
        return await self._execute_request(path, "GET", params=params, api=api)

    async def _post_request(self, path: str, body: dict, api: bool = True) -> dict:
        return await self._execute_request(path, "POST", body=body, api=api)

    async def complete_login(
        self,
        credentials: EntityCredentials,
        login_options: LoginOptions,
        session: Optional[EntitySession] = None,
    ) -> EntityLoginResult:
        logging_in = len(credentials) > 0
        if not logging_in and not self._alive_session(session):
            if login_options.avoid_new_login:
                return EntityLoginResult(code=LoginResultCode.NOT_LOGGED)

            return EntityLoginResult(code=LoginResultCode.MANUAL_LOGIN)

        self._genoma_session = new_impersonated_http_session()
        self._api_session = new_impersonated_http_session()

        now = datetime.now(tzlocal())
        if session and not login_options.force_new_session and now < session.expiration:
            self.inject_session(session.payload)
            if await self._resumable_session():
                return EntityLoginResult(LoginResultCode.RESUMED)

        if not logging_in:
            return EntityLoginResult(LoginResultCode.MANUAL_LOGIN)

        try:
            self.inject_session(credentials)
            try:
                await self.get_position()
            except httpx.NetworkError as e:
                if "request timed out" in str(e):
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR,
                        message="Bad fingerprint or network issues",
                    )
                else:
                    raise

            self._session_expiration = datetime.now(tzlocal()) + timedelta(
                seconds=SESSION_LIFETIME
            )
            new_session = EntitySession(
                creation=datetime.now(tzlocal()),
                expiration=self._session_expiration,
                payload=credentials,
            )

            return EntityLoginResult(LoginResultCode.CREATED, session=new_session)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

            return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR)

    @staticmethod
    def _alive_session(session: EntitySession) -> bool:
        return session is not None and datetime.now(tzlocal()) < session.expiration

    async def _resumable_session(self) -> bool:
        try:
            await self.get_position()
        except httpx.HTTPStatusError:
            return False
        else:
            return True

    def inject_session(self, payload: dict):
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36"
        self._genoma_session.headers["Content-Type"] = "application/json"
        self._genoma_session.headers["Cookie"] = payload["genomaCookie"]
        self._genoma_session.headers["genoma-session-id"] = payload["genomaSessionId"]
        self._genoma_session.headers["User-Agent"] = user_agent

        self._api_session.headers["Content-Type"] = "application/json; charset=utf-8"
        self._api_session.headers["Cookie"] = payload["apiCookie"]
        self._api_session.headers["Authorization"] = payload["apiAuth"]
        self._api_session.headers["X-ING-ExtendedSessionContext"] = payload[
            "apiExtendedSessionCtx"
        ]
        self._api_session.headers["User-Agent"] = user_agent

        self._genoma_login_session = None
        genoma_login_cookie = payload.get("genomaLoginCookie")
        if genoma_login_cookie:
            self._genoma_login_session = new_impersonated_http_session()
            self._genoma_login_session.headers["Cookie"] = genoma_login_cookie
            self._genoma_login_session.headers["User-Agent"] = user_agent

    def supports_sca(self) -> bool:
        return self._genoma_login_session is not None

    def _xsrf_token(self) -> Optional[str]:
        cookie_header = self._genoma_session.headers.get("Cookie") or ""
        for cookie in cookie_header.split(";"):
            name, _, value = cookie.strip().partition("=")
            if name == "XSRF-TOKEN" and value:
                return value
        return None

    async def start_sca(self) -> dict:
        return await self._execute_request(
            "/sca/documentation",
            "GET",
            api=False,
            headers={"X-Ing-Reset-Validations": "1"},
        )

    async def get_sca_status(self, security_process_id: str) -> dict:
        return await self._send(
            self._genoma_login_session,
            "GET",
            self.GENOMA_LOGIN_BASE_URL + "/getScaStatus",
            params={
                "secProcessId": security_process_id,
                "isLogin": "false",
                "device": "false",
                "model": "false",
                "version": "false",
            },
            timeout=SCA_STATUS_TIMEOUT,
        )

    async def confirm_sca(self, security_process_id: str) -> dict:
        headers = {"X-Ing-Securityprocessid": security_process_id}
        xsrf_token = self._xsrf_token()
        if xsrf_token:
            headers["X-XSRF-TOKEN"] = xsrf_token
        return await self._execute_request(
            "/sca/documentation",
            "PUT",
            body={"processId": security_process_id},
            api=False,
            headers=headers,
        )

    async def synchronize_access_token(self) -> bool:
        response = await self._get_request("/saf/tpa/accesstoken/synchronize")
        tokens = response.get("accessTokens") or []
        access_token = tokens[0].get("accessToken") if tokens else None
        if not access_token:
            return False
        current = self._api_session.headers.get("Authorization") or ""
        scheme = current.split(" ", 1)[0] if " " in current else "Bearer"
        self._api_session.headers["Authorization"] = f"{scheme} {access_token}"
        return True

    async def get_user(self) -> dict:
        return await self._get_request("/client", api=False)

    @cached(cache=Cache.MEMORY, ttl=30)
    async def get_position(self) -> dict:
        return await self._get_request("/position-keeping")

    @cached(cache=Cache.MEMORY, ttl=30)
    async def get_orders(
        self,
        product_id: str,
        type: Optional[str] = "history",
        order_status: Optional[str] = None,
        offset: int = 0,
        limit: int = 1000,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> dict:  # returns {elements[], limit, offset, count, total}
        to_date = to_date or datetime.now().date()
        params = {
            "type": type,  # day orders if not provided
            "orderStatus": order_status,
            "offset": offset,
            "limit": limit,
        }
        if from_date:
            params["fromDate"] = from_date.strftime(DATE_FORMAT)
        if to_date:
            params["toDate"] = to_date.strftime(DATE_FORMAT)

        return await self._get_request(
            f"/products/{product_id}/orders",
            params=params,
            api=False,
        )

    @cached(cache=Cache.MEMORY, ttl=120)
    async def get_broker_order(self, market_code: str, order_id: str) -> dict:
        return await self._get_request(
            f"/broker/order/history/detail?marketCod={market_code}&orderId={order_id}",
            api=False,
        )

    @cached(cache=Cache.MEMORY, ttl=120)
    async def get_movements(
        self,
        product_id: str,
        from_date: date,
        offset: int = 0,
        limit: int = 100,
        to_date: Optional[date] = None,
    ) -> dict:
        to_date = to_date or datetime.now().date()
        return await self._get_request(
            f"/products/{product_id}/movements",
            params={
                "offset": offset,
                "limit": limit,
                "fromDate": from_date.strftime(DATE_FORMAT) if from_date else None,
                "toDate": to_date.strftime(DATE_FORMAT) if to_date else None,
            },
            api=False,
        )

    @cached(cache=Cache.MEMORY, ttl=120)
    async def get_account_transactions(
        self,
        product_id: str,
        from_date: date,
        offset: int = 0,
        limit: int = 100,
        to_date: Optional[date] = None,
    ) -> dict:
        to_date = to_date or datetime.now(tzlocal()).date()
        return await self._get_request(
            f"/v2/products/{product_id}/transactions",
            params={
                "limit": limit,
                "offset": offset,
                "fromDate": from_date.strftime(DASHED_DATE_FORMAT),
                "toDate": to_date.strftime(DASHED_DATE_FORMAT),
                "filterEru": "false",
            },
        )

    @cached(cache=Cache.MEMORY, ttl=120)
    async def get_broker_portfolio(self, product_id: str) -> dict:
        return await self._get_request(f"/products/{product_id}/portfolio", api=False)

    @cached(cache=Cache.MEMORY, ttl=120)
    async def get_broker_financial_events(self, product_id: str) -> dict:
        return await self._get_request(
            f"/products/{product_id}/financialEvents", api=False
        )

    @cached(cache=Cache.MEMORY, ttl=86400)
    async def get_investment_catalog_products(self) -> dict:
        return await self._get_request(
            "/investment-product-offering-portfolio/v1/catalog-products?size=1000"
        )

    @cached(cache=Cache.MEMORY, ttl=86400)
    async def get_investment_product_details(self, product_code: str) -> dict:
        return await self._get_request(
            f"/investment-product-offering-portfolio/v1/catalog-products/{product_code}"
        )

    @cached(cache=Cache.MEMORY, ttl=86400)
    async def get_investment_product_details_v2(self, product_code: str) -> dict:
        return await self._get_request(
            f"/investment-product-offering-portfolio/v2/products/{product_code}"
        )

    @cached(cache=Cache.MEMORY, ttl=86400)
    async def get_fund_documents(self, product_subtype: str, product_type: str) -> dict:
        return await self._get_request(
            f"/investment/doc/{product_type}/legal/{product_subtype}", api=False
        )

    @cached(cache=Cache.MEMORY, ttl=86400)
    async def get_customer_investment_reporting(
        self, family: str, start_date: date, end_date: date
    ) -> dict:
        return await self._get_request(
            "/customer-investment-reporting/v2/investment-report",
            params={
                "families": family,
                "allProducts": "true",
                "startDate": start_date.strftime(DASHED_DATE_FORMAT),
                "endDate": end_date.strftime(DASHED_DATE_FORMAT),
            },
        )
