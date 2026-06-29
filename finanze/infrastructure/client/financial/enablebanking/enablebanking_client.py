import logging
import time
from typing import Optional

import httpx
import jwt
from aiocache import Cache
from aiocache.serializers import PickleSerializer
from application.ports.connectable_integration import ConnectableIntegration
from domain.exception.exceptions import (
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    TooManyRequests,
)
from domain.external_integration import ExternalIntegrationPayload
from infrastructure.client.http.http_session import get_http_session


class EnableBankingClient(ConnectableIntegration):
    BASE_URL = "https://api.enablebanking.com"
    REDIRECT_URL = "https://finanze.me/eb/v1/entity/callback/"
    JWT_ISSUER = "enablebanking.com"
    JWT_AUDIENCE = "api.enablebanking.com"
    JWT_TTL_SECONDS = 3600
    ASPSPS_TTL = 86400
    REQUEST_TIMEOUT = 30
    DEFAULT_PSU_TYPE = "personal"

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._session = get_http_session()
        self._application_id: Optional[str] = None
        self._private_key: Optional[str] = None
        self._cache = Cache(Cache.MEMORY, serializer=PickleSerializer())

    async def setup(self, credentials: ExternalIntegrationPayload) -> None:
        application_id = credentials.get("application_id")
        private_key = credentials.get("private_key")
        if not application_id or not private_key:
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)

        self._application_id = application_id
        self._private_key = private_key

        try:
            await self.get_application()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            self._log.error("Error validating Enable Banking credentials: %s", status)
            if status in (401, 403):
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.INVALID_CREDENTIALS
                ) from e
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN) from e
        except IntegrationSetupError:
            raise
        except Exception as e:
            self._log.exception("Unexpected error during Enable Banking setup")
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN) from e

    def _build_jwt(self) -> str:
        if not self._application_id or not self._private_key:
            raise ValueError("Client not set up. Call setup() first.")

        now = int(time.time())
        headers = {"typ": "JWT", "alg": "RS256", "kid": self._application_id}
        payload = {
            "iss": self.JWT_ISSUER,
            "aud": self.JWT_AUDIENCE,
            "iat": now,
            "exp": now + self.JWT_TTL_SECONDS,
        }
        try:
            return jwt.encode(
                payload, self._private_key, algorithm="RS256", headers=headers
            )
        except Exception as e:
            self._log.error("Failed to build Enable Banking JWT: %s", e)
            raise IntegrationSetupError(
                IntegrationSetupErrorCode.INVALID_CREDENTIALS
            ) from e

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._build_jwt()}",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict:
        url = f"{self.BASE_URL}{path}"
        try:
            response = await self._session.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._auth_headers(),
                timeout=self.REQUEST_TIMEOUT,
            )
        except (httpx.RequestError, TimeoutError) as e:
            self._log.error("Request error calling Enable Banking %s: %s", url, e)
            raise

        if not response.ok:
            if response.status == 429:
                raise TooManyRequests()
            body = await response.text()
            self._log.error(
                "Error calling Enable Banking %s: %s %s", url, response.status, body
            )
            response.raise_for_status()

        return await response.json()

    async def get_application(self) -> dict:
        return await self._request("GET", "/application")

    async def get_aspsps(self, country: str) -> list[dict]:
        cache_key = f"aspsps:{country}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._request("GET", "/aspsps", params={"country": country})
        aspsps = data.get("aspsps", [])
        await self._cache.set(cache_key, aspsps, ttl=self.ASPSPS_TTL)
        return aspsps

    async def start_auth(
        self,
        aspsp_name: str,
        aspsp_country: str,
        state: str,
        valid_until: str,
        psu_type: str = DEFAULT_PSU_TYPE,
    ) -> dict:
        body = {
            "access": {"valid_until": valid_until},
            "aspsp": {"name": aspsp_name, "country": aspsp_country},
            "state": state,
            "redirect_url": self.REDIRECT_URL,
            "psu_type": psu_type,
        }
        return await self._request("POST", "/auth", json=body)

    async def create_session(self, code: str) -> dict:
        return await self._request("POST", "/sessions", json={"code": code})

    async def get_session(self, session_id: str) -> dict:
        return await self._request("GET", f"/sessions/{session_id}")

    async def get_account_balances(self, account_uid: str) -> dict:
        return await self._request("GET", f"/accounts/{account_uid}/balances")

    async def delete_session(self, session_id: str) -> dict:
        return await self._request("DELETE", f"/sessions/{session_id}")
