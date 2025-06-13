import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from cachetools import TTLCache, cached
from dateutil.tz import tzlocal

from domain.entity_login import EntityLoginResult, LoginResultCode


def _is_selenium_available() -> bool:
    try:
        import selenium  # noqa: F401

        return True
    except ImportError:
        return False


SESSION_LIFETIME = 14 * 60  # 15 minutes - 1 minute of tolerance


class MintosAPIClient:
    BASE_URL = "https://www.mintos.com"
    BASE_API_URL = f"{BASE_URL}/webapp/api"
    USER_PATH = f"{BASE_API_URL}/en/webapp-api/user"

    def __init__(self):
        self._session = requests.Session()
        self._log = logging.getLogger(__name__)
        self._automated_login = _is_selenium_available()
        self._session_expiration = None

    @property
    def automated_login(self) -> bool:
        return self._automated_login

    def _execute_request(
        self,
        path: str,
        method: str,
        body: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        response = self._session.request(
            method, self.BASE_API_URL + path, json=body, params=params
        )

        if response.ok:
            return response.json()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}

    def _get_request(self, path: str, params: dict = None) -> dict | str:
        return self._execute_request(path, "GET", params=params)

    def _post_request(self, path: str, body: dict) -> dict | requests.Response:
        return self._execute_request(path, "POST", body=body)

    def has_completed_login(self) -> bool:
        return (
            "Cookie" in self._session.headers
            and self._session_expiration is not None
            and datetime.now(tzlocal()) <= self._session_expiration
        )

    def complete_login(self, cookie_header: Optional[str] = None):
        if cookie_header:
            self._session.headers["Cookie"] = cookie_header
            self._session_expiration = datetime.now(tzlocal()) + timedelta(
                seconds=SESSION_LIFETIME
            )

        try:
            self.get_user()
            return EntityLoginResult(LoginResultCode.CREATED)

        except requests.HTTPError as e:
            if e.response.status_code == 403:
                return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

            return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR)

    async def login(self, username: str, password: str) -> EntityLoginResult:
        from infrastructure.scrapers.mintos.mintos_selenium_login_client import login

        return await login(self._log, self.complete_login, username, password)

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_user(self) -> dict:
        return self._get_request("/en/webapp-api/user")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_overview(self, wallet_currency_id) -> dict:
        return self._get_request(
            f"/marketplace-api/v1/user/overview/currency/{wallet_currency_id}"
        )

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_net_annual_returns(self, wallet_currency_id) -> dict:
        return self._get_request(
            f"/en/webapp-api/user/overview-net-annual-returns?currencyIsoCode={wallet_currency_id}"
        )

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_portfolio(self, wallet_currency_id) -> dict:
        return self._get_request(
            f"/marketplace-api/v1/user/overview/currency/{wallet_currency_id}/portfolio-data"
        )
