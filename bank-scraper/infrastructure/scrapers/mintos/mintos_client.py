import logging
from typing import Union, Optional

import requests
from cachetools import TTLCache, cached

from domain.login import LoginResult


class MintosAPIClient:
    BASE_URL = "https://www.mintos.com"
    BASE_API_URL = f"{BASE_URL}/webapp/api"
    USER_PATH = f"{BASE_API_URL}/en/webapp-api/user"

    def __init__(self):
        self._session = requests.Session()
        self._log = logging.getLogger(__name__)

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

        self._log.error("Error Response Body:", response.text)
        response.raise_for_status()
        return {}

    def _get_request(
            self, path: str, params: dict = None
    ) -> Union[dict, str]:
        return self._execute_request(path, "GET", params=params)

    def _post_request(
            self, path: str, body: dict
    ) -> Union[dict, requests.Response]:
        return self._execute_request(path, "POST", body=body)

    async def login(self, username: str, password: str) -> LoginResult:
        from infrastructure.scrapers.mintos.mintos_selenium_login_client import login
        return await login(self._log, self._session, username, password)

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_user(self) -> dict:
        return self._get_request("/en/webapp-api/user")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_overview(self, wallet_currency_id) -> dict:
        return self._get_request(f"/marketplace-api/v1/user/overview/currency/{wallet_currency_id}")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_net_annual_returns(self, wallet_currency_id) -> dict:
        return self._get_request(
            f"/en/webapp-api/user/overview-net-annual-returns?currencyIsoCode={wallet_currency_id}")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_portfolio(self, wallet_currency_id) -> dict:
        return self._get_request(f"/marketplace-api/v1/user/overview/currency/{wallet_currency_id}/portfolio-data")
