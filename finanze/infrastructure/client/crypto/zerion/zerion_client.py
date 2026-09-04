import asyncio
import base64
import logging
from urllib.parse import quote

from application.ports.connectable_integration import ConnectableIntegration
from domain.exception.exceptions import (
    AddressNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    TooManyRequests,
)
from domain.external_integration import ExternalIntegrationPayload
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.client.http.http_session import get_http_session

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class ZerionClient(ConnectableIntegration):
    BASE_URL = "https://api.zerion.io/v1"
    MAX_RETRIES = 3
    BACKOFF_SECONDS = 0.5
    RETRYABLE_STATUSES = (429, 503)
    MAX_RETRY_AFTER_SECONDS = 30.0

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._session = get_http_session()

    async def setup(self, credentials: ExternalIntegrationPayload) -> None:
        api_key = credentials["api_key"]
        response = await self._get(f"{self.BASE_URL}/chains/", api_key)

        if response.status in (401, 403):
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)
        if response.status == 429:
            raise TooManyRequests()
        if not response.ok:
            body = await response.text()
            self._log.error(
                f"Error validating Zerion API key: {response.status} {body}"
            )
            response.raise_for_status()

    async def fetch_positions(
        self,
        api_key: str,
        address: str,
        positions_filter: str = "only_complex",
    ) -> list[dict]:
        url = (
            f"{self.BASE_URL}/wallets/{quote(address, safe='')}/positions/"
            f"?filter[positions]={positions_filter}"
            "&filter[trash]=only_non_trash"
            "&currency=eur"
        )
        response = await self._get(url, api_key)

        if response.status in (401, 403):
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)
        if response.status == 429:
            raise TooManyRequests()
        if response.status == 400:
            # Zerion returns HTTP 200 for any valid address (even one with no
            # positions) and 400 for a malformed/invalid one - it never 404s.
            # Treat it as a per-address miss so one bad address doesn't abort
            # the whole entity fetch.
            raise AddressNotFound()
        if not response.ok:
            body = await response.text()
            self._log.error(
                f"Error fetching Zerion positions: {response.status} {body}"
            )
            response.raise_for_status()

        data = await response.json()
        return data.get("data", [])

    async def _get(self, url: str, api_key: str) -> HttpResponse:
        headers = self._headers(api_key)
        attempt = 0
        while True:
            response = await self._session.get(url, headers=headers)
            if (
                response.status not in self.RETRYABLE_STATUSES
                or attempt >= self.MAX_RETRIES
            ):
                return response
            attempt += 1
            await asyncio.sleep(self._retry_delay(response))

    def _retry_delay(self, response: HttpResponse) -> float:
        # Zerion answers 503 + Retry-After while a wallet is still being indexed.
        if response.status == 503:
            retry_after = self._retry_after_seconds(response)
            if retry_after is not None:
                return min(retry_after, self.MAX_RETRY_AFTER_SECONDS)
        return self.BACKOFF_SECONDS

    @staticmethod
    def _retry_after_seconds(response: HttpResponse) -> float | None:
        value = next(
            (
                v
                for k, v in (response.headers or {}).items()
                if k.lower() == "retry-after"
            ),
            None,
        )
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return None
        return seconds if seconds > 0 else None

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        token = base64.b64encode(f"{api_key}:".encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "User-Agent": USER_AGENT,
        }
