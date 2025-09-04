import logging
from datetime import date, datetime, timedelta
from typing import Optional

import requests
from cachetools import TTLCache, cached
from dateutil.tz import tzlocal
from domain.entity import EntityCredentials
from domain.entity_login import (
    EntityLoginResult,
    EntitySession,
    LoginOptions,
    LoginResultCode,
)

SESSION_LIFETIME = 4 * 60  # 4 minutes

DATE_FORMAT = "%d/%m/%Y"


class INGAPIClient:
    GENOMA_BASE_URL = "https://ing.ingdirect.es/genoma_api/rest"
    API_BASE_URL = "https://api.ing.ingdirect.es"

    def __init__(self):
        self._genoma_session = None
        self._api_session = None
        self._session_expiration = None

        self._log = logging.getLogger(__name__)

    def _execute_request(
        self,
        path: str,
        method: str,
        body: Optional[dict] = None,
        params: Optional[dict] = None,
        api: bool = True,
    ) -> dict:
        base_url = self.API_BASE_URL if api else self.GENOMA_BASE_URL
        session = self._api_session if api else self._genoma_session
        response = session.request(method, base_url + path, json=body, params=params)

        if response.ok:
            return response.json()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}

    def _get_request(self, path: str, params: dict = None, api: bool = True) -> dict:
        return self._execute_request(path, "GET", params=params, api=api)

    def _post_request(
        self, path: str, body: dict, api: bool = True
    ) -> dict | requests.Response:
        return self._execute_request(path, "POST", body=body, api=api)

    def complete_login(
        self,
        credentials: EntityCredentials,
        login_options: LoginOptions,
        session: Optional[EntitySession] = None,
    ) -> EntityLoginResult:
        logging_in = len(credentials) > 0
        if not logging_in and session is None:
            if login_options.avoid_new_login:
                return EntityLoginResult(code=LoginResultCode.NOT_LOGGED)

            return EntityLoginResult(code=LoginResultCode.MANUAL_LOGIN)

        self._genoma_session = requests.Session()
        self._api_session = requests.Session()

        now = datetime.now(tzlocal())
        if session and not login_options.force_new_session and now < session.expiration:
            self.inject_session(session.payload)
            if self._resumable_session():
                return EntityLoginResult(LoginResultCode.RESUMED)

        if not logging_in:
            return EntityLoginResult(LoginResultCode.MANUAL_LOGIN)

        try:
            self.inject_session(credentials)
            self.get_user()

            self._session_expiration = datetime.now(tzlocal()) + timedelta(
                seconds=SESSION_LIFETIME
            )
            new_session = EntitySession(
                creation=datetime.now(tzlocal()),
                expiration=self._session_expiration,
                payload=credentials,
            )

            return EntityLoginResult(LoginResultCode.CREATED, session=new_session)

        except requests.HTTPError as e:
            if e.response.status_code == 403:
                return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

            return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR)

    def _resumable_session(self) -> bool:
        try:
            self.get_user()
        except requests.exceptions.HTTPError:
            return False
        else:
            return True

    def inject_session(self, payload: dict):
        self._genoma_session.headers["Content-Type"] = "application/json"
        self._genoma_session.headers["Cookie"] = payload["genomaCookie"]
        self._genoma_session.headers["genoma-session-id"] = payload["genomaSessionId"]

        self._api_session.headers["Content-Type"] = "application/json; charset=utf-8"
        self._api_session.headers["Cookie"] = payload["apiCookie"]
        self._api_session.headers["Authorization"] = payload["apiAuth"]
        self._api_session.headers["X-ING-ExtendedSessionContext"] = payload[
            "apiExtendedSessionCtx"
        ]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_user(self) -> dict:
        return self._get_request("/client", api=False)

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_position(self) -> dict:
        return self._get_request("/position-keeping")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_orders(
        self,
        product_id: str,
        from_date: date,
        offset: int = 0,
        limit: int = 1000,
        to_date: Optional[date] = None,
    ) -> dict:  # returns {elements[], limit, offset, count, total}
        to_date = to_date or datetime.now().date()
        return self._get_request(
            f"/products/{product_id}/orders",
            params={
                "type": "history",  # day orders if not provided
                "offset": offset,
                "limit": limit,
                "fromDate": from_date.strftime(DATE_FORMAT) if from_date else None,
                "toDate": to_date.strftime(DATE_FORMAT) if to_date else None,
            },
            api=False,
        )

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_broker_order(self, market_code: str, order_id: str) -> dict:
        return self._get_request(
            f"/broker/order/history/detail?marketCod={market_code}&orderId={order_id}",
            api=False,
        )

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_movements(
        self,
        product_id: str,
        from_date: date,
        offset: int = 0,
        limit: int = 100,
        to_date: Optional[date] = None,
    ) -> dict:
        to_date = to_date or datetime.now().date()
        return self._get_request(
            f"/products/{product_id}/movements",
            params={
                "offset": offset,
                "limit": limit,
                "fromDate": from_date.strftime(DATE_FORMAT) if from_date else None,
                "toDate": to_date.strftime(DATE_FORMAT) if to_date else None,
            },
            api=False,
        )

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_broker_portfolio(self, product_id: str) -> dict:
        return self._get_request(f"/products/{product_id}/portfolio")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_broker_financial_events(self, product_id: str) -> dict:
        return self._get_request(f"/products/{product_id}/financialEvents")
