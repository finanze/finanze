import logging

import requests
from cachetools import cached, TTLCache

from domain.entity_login import LoginResultCode, EntityLoginResult


class IndexaCapitalClient:
    BASE_URL = "https://api.indexacapital.com"

    def __init__(self):
        self._headers = {}
        self._log = logging.getLogger(__name__)

    def _execute_request(self, path: str, method: str, body: dict | None = None,
                         raw: bool = False) -> dict | requests.Response:
        response = requests.request(
            method, self.BASE_URL + path, json=body, headers=self._headers
        )
        if raw:
            return response
        if response.ok:
            return response.json()
        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}

    def _get_request(self, path: str) -> dict:
        return self._execute_request(path, "GET", body=None)

    def setup(self, token: str) -> EntityLoginResult:
        self._headers["X-AUTH-TOKEN"] = token

        response = self._execute_request("/users/me", "GET", raw=True)
        if response.ok:
            return EntityLoginResult(LoginResultCode.CREATED)
        elif response.status_code == 401 or response.status_code == 403:
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
        else:
            return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR,
                                     message=f"Got unexpected response code {response.status_code}")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_user_info(self) -> dict:
        return self._get_request("/users/me")

    def get_account(self, account_number: str) -> dict:
        return self._get_request(f"/accounts/{account_number}")

    def get_portfolio(self, account_number: str) -> dict:
        return self._get_request(f"/accounts/{account_number}/portfolio")
