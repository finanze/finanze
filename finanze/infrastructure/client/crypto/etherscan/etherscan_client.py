import logging
from typing import Optional

import httpx

from aiocache import Cache
from aiocache.serializers import PickleSerializer

from application.ports.connectable_integration import ConnectableIntegration
from domain.exception.exceptions import (
    AddressNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    TooManyRequests,
)
from domain.external_integration import (
    ExternalIntegrationPayload,
)
from infrastructure.client.http.backoff import http_get_with_backoff
from infrastructure.client.http.http_session import get_http_session
from infrastructure.client.http.http_response import HttpResponse


class EtherscanClient(ConnectableIntegration):
    TTL = 60
    BASE_URL = "https://api.etherscan.io/v2/api?"
    COOLDOWN = 0.2
    MAX_RETRIES = 4
    BACKOFF_BASE = 2.6
    BACKOFF_FACTOR = 1

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._cache = Cache(Cache.MEMORY, serializer=PickleSerializer())
        self._session = get_http_session()

    async def setup(self, credentials: ExternalIntegrationPayload):
        await self.fetch(
            chain_id=1,
            module="stats",
            action="ethprice",
            credentials=credentials,
        )

    async def fetch(
        self,
        chain_id: int,
        module: str,
        action: str,
        credentials: ExternalIntegrationPayload,
        address: Optional[str] = None,
        contract_address: Optional[str] = None,
        sort: Optional[str] = None,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
    ):
        api_key = credentials["api_key"]
        params = f"chainid={chain_id}&module={module}&action={action}&apikey={api_key}&tag=latest"
        if address:
            params = f"{params}&address={address}"
        if contract_address:
            params = f"{params}&contractaddress={contract_address}"
        if sort:
            params = f"{params}&sort={sort}"
        if start_block:
            params = f"{params}&startblock={start_block}"
        if end_block:
            params = f"{params}&endblock={end_block}"

        cached_value = await self._cache.get(params)
        if cached_value is not None:
            return cached_value

        result = await self._fetch_uncached(params)
        await self._cache.set(params, result, ttl=self.TTL)
        return result

    async def _fetch_uncached(self, path: str):
        url = self.BASE_URL + path

        async def _should_retry(resp: HttpResponse, attempt: int) -> bool:
            try:
                data = await resp.json()
            except ValueError:
                return False
            status = data.get("status")
            result = data.get("result")
            if status == "0" and isinstance(result, str):
                lowered = result.lower()
                if "max calls" in lowered or "free api access" in lowered:
                    return True
            return False

        try:
            response = await http_get_with_backoff(
                url,
                cooldown=self.COOLDOWN,
                max_retries=self.MAX_RETRIES,
                backoff_exponent_base=self.BACKOFF_BASE,
                backoff_factor=self.BACKOFF_FACTOR,
                log=self._log,
                should_retry=_should_retry,
            )
        except (httpx.RequestError, TimeoutError) as e:
            self._log.error(f"Request error calling Etherscan endpoint {url}: {e}")
            raise

        if not response.ok:
            if response.status == 429:
                raise TooManyRequests()
            body = await response.text()
            self._log.error(f"Error fetching from Etherscan: {response.status} {body}")
            response.raise_for_status()

        data = await response.json()
        status = data.get("status")
        result = data.get("result")
        msg = data.get("message", "")
        if status == "0":
            if result and "Invalid API Key" in result:
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.INVALID_CREDENTIALS
                )
            if result and ("Max calls" in result or "Free API access" in result):
                raise TooManyRequests()
            if "No transactions found" in msg:
                raise AddressNotFound()
            if "timeout" in str(msg).lower():
                raise ValueError("Request timed out")

            self._log.error(
                f"Error fetching from Etherscan: {response.status} {await response.text()}"
            )
            raise ValueError(result or msg)

        return result
