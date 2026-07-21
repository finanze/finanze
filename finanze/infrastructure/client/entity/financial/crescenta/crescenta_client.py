import base64
import logging

from domain.entity_login import EntityLoginResult, LoginResultCode
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.client.http.http_session import get_http_session


class CrescentaClient:
    BASE_URL = "https://gateway.crescenta.com"
    CLIENT_ID = "app"
    CLIENT_SECRET = "bneo-secret"

    def __init__(self):
        self._headers = {"X-Tenant-Id": "minerva"}
        self._log = logging.getLogger(__name__)
        self._session = get_http_session()

    @staticmethod
    def _basic_auth() -> str:
        credentials = (
            f"{CrescentaClient.CLIENT_ID}:{CrescentaClient.CLIENT_SECRET}".encode(
                "utf-8"
            )
        )
        return f"Basic {base64.b64encode(credentials).decode('utf-8')}"

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

    async def login(self, username: str, password: str) -> EntityLoginResult:
        self._headers.pop("Authorization", None)
        form_data = {
            "grant_type": "password",
            "username": username,
            "password": password,
        }
        response = await self._session.request(
            "POST",
            self.BASE_URL + "/uaa/oauth/token",
            data=form_data,
            headers={**self._headers, "Authorization": self._basic_auth()},
        )
        body_text = await response.text()
        if response.status == 401:
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
        if not response.ok:
            self._log.error(f"Unexpected login response {response.status}: {body_text}")
            if response.status == 400 and "invalid_grant" in body_text:
                return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Unexpected login response {response.status}",
            )
        body = await response.json()
        access_token = body.get("access_token")
        if not access_token:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="Missing access_token in login response",
            )
        self._headers["Authorization"] = f"Bearer {access_token}"
        return EntityLoginResult(LoginResultCode.CREATED)

    async def get_current_account(self) -> dict:
        return await self._get_request("/accounts/current")

    async def get_flow_data(self, account_id: str) -> dict:
        return await self._get_request(f"/invests/flowdata/{account_id}")

    async def get_portfolio_data(self, portfolio_id: str) -> dict:
        return await self._get_request(
            f"/invests/alternativeFundsPortfolio/{portfolio_id}/portfolioData"
        )

    async def get_movements(self, account_id: str) -> dict:
        return await self._get_request(
            f"/invests/movements/filter?accountId={account_id}"
        )

    async def get_product_details(self, account_id: str, product_id: str) -> dict:
        return await self._get_request(
            f"/products/alternative/{account_id}/{product_id}/details"
        )
