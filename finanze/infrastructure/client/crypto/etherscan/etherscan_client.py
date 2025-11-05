import logging
from typing import Optional

import requests
from application.ports.connectable_integration import ConnectableIntegration
from cachetools import TTLCache
from domain.exception.exceptions import (
    AddressNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    TooManyRequests,
)
from domain.external_integration import EtherscanIntegrationData
from infrastructure.client.http.backoff import http_get_with_backoff


class EtherscanClient(ConnectableIntegration[EtherscanIntegrationData]):
    TTL = 60
    BASE_URL = "https://api.etherscan.io/v2/api?"
    COOLDOWN = 0.2
    MAX_RETRIES = 3
    BACKOFF_BASE = 2.6
    BACKOFF_FACTOR = 0.8

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._cache = TTLCache(maxsize=50, ttl=self.TTL)

    def setup(self, credentials: EtherscanIntegrationData):
        self.fetch(
            chain_id=1,
            module="stats",
            action="ethsupply",
            credentials=credentials,
        )

    def fetch(
        self,
        chain_id: int,
        module: str,
        action: str,
        credentials: EtherscanIntegrationData,
        address: Optional[str] = None,
        contract_address: Optional[str] = None,
        sort: Optional[str] = None,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
    ):
        params = f"chainid={chain_id}&module={module}&action={action}&apikey={credentials.api_key}&tag=latest"
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

        cached_value = self._cache.get(params)
        if cached_value is not None:
            return cached_value
        result = self._fetch_uncached(params)
        self._cache[params] = result
        return result

    def _fetch_uncached(self, path: str):
        url = self.BASE_URL + path

        def _should_retry(resp: requests.Response, attempt: int) -> bool:
            try:
                data = resp.json()
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
            response = http_get_with_backoff(
                url,
                cooldown=self.COOLDOWN,
                max_retries=self.MAX_RETRIES,
                backoff_exponent_base=self.BACKOFF_BASE,
                backoff_factor=self.BACKOFF_FACTOR,
                log=self._log,
                should_retry=_should_retry,
            )
        except requests.RequestException as e:
            self._log.error(f"Request error calling Etherscan endpoint {url}: {e}")
            raise

        if not response.ok:
            if response.status_code == 429:
                raise TooManyRequests()
            self._log.error(
                f"Error fetching from Etherscan: {response.status_code} {response.text}"
            )
            response.raise_for_status()

        data = response.json()
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
            if "timeout" in msg.lower():
                raise ValueError("Request timed out")

            self._log.error(
                f"Error fetching from Etherscan: {response.status_code} {response.text}"
            )
            raise ValueError(result or msg)

        return result
