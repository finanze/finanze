import logging
import time
from typing import Optional

import requests
from application.ports.connectable_integration import ConnectableIntegration
from cachetools import TTLCache, cached
from domain.exception.exceptions import IntegrationSetupError, TooManyRequests
from domain.external_integration import EtherscanIntegrationData


class EtherscanClient(ConnectableIntegration[EtherscanIntegrationData]):
    TTL = 60
    BASE_URL = "https://api.etherscan.io/v2/api?"
    COOLDOWN = 0.19

    def __init__(self):
        self._log = logging.getLogger(__name__)

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
    ) -> any:
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

        return self._fetch(params)

    @cached(cache=TTLCache(maxsize=50, ttl=TTL))
    def _fetch(self, path: str) -> any:
        response = requests.get(self.BASE_URL + path)

        if not response.ok:
            if response.status_code == 429:
                raise TooManyRequests()

            self._log.error(
                f"Error fetching from Etherscan: {response.status_code} {response.text}"
            )
            response.raise_for_status()

        data = response.json()
        status = data["status"]
        result = data["result"]
        if status == "0":
            if result and "Invalid API Key" in result:
                raise IntegrationSetupError("Invalid API Key")
            elif result and "Max calls" in result:
                raise TooManyRequests()
            else:
                raise ValueError()

        time.sleep(self.COOLDOWN)

        return result
