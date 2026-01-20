import logging

from aiocache import cached, Cache
from domain.entity_login import EntityLoginResult, LoginResultCode
from infrastructure.client.http.http_session import get_http_session
from infrastructure.client.http.http_response import HttpResponse


class IndexaCapitalClient:
    BASE_URL = "https://api.indexacapital.com"

    def __init__(self):
        self._headers = {}
        self._log = logging.getLogger(__name__)
        self._session = get_http_session()

    async def _execute_request(
        self, path: str, method: str, body: dict | None = None, raw: bool = False
    ) -> dict | HttpResponse:
        response = await self._session.request(
            method, self.BASE_URL + path, json=body, headers=self._headers
        )
        if raw:
            return response
        if response.ok:
            return await response.json()
        body_text = await response.text()
        self._log.error("Error Response Body:" + body_text)
        response.raise_for_status()
        return {}

    async def _get_request(self, path: str) -> dict:
        return await self._execute_request(path, "GET", body=None)

    async def setup(self, token: str) -> EntityLoginResult:
        self._headers["X-AUTH-TOKEN"] = token

        response = await self._execute_request("/users/me", "GET", raw=True)
        if response.ok:
            return EntityLoginResult(LoginResultCode.CREATED)
        elif response.status == 401 or response.status == 403:
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
        else:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected response code {response.status}",
            )

    @cached(cache=Cache.MEMORY, ttl=120)
    async def get_user_info(self) -> dict:
        return await self._get_request("/users/me")

    async def get_account(self, account_number: str) -> dict:
        return await self._get_request(f"/accounts/{account_number}")

    async def get_portfolio(self, account_number: str) -> dict:
        return await self._get_request(f"/accounts/{account_number}/portfolio")

    async def get_instrument_transactions(self, account_number: str) -> dict:
        return await self._get_request(
            f"/accounts/{account_number}/instrument-transactions"
        )

    async def get_cash_transactions(self, account_number: str) -> dict:
        return await self._get_request(f"/accounts/{account_number}/cash-transactions")
