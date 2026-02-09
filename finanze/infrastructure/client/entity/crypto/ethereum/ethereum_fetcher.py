import logging

from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from domain.crypto import CryptoFetchRequest
from domain.dezimal import Dezimal
from domain.external_integration import ExternalIntegrationId
from domain.global_position import (
    CryptoCurrencyWallet,
)
from infrastructure.client.crypto.etherscan.etherscan_client import EtherscanClient
from infrastructure.client.crypto.etherscan.etherscan_fetcher import EtherscanFetcher
from infrastructure.client.crypto.ethplorer.ethplorer_client import EthplorerClient
from infrastructure.client.crypto.ethplorer.ethplorer_fetcher import EthplorerFetcher


class EthereumFetcher(CryptoEntityFetcher):
    ETHERSCAN_CHAIN_ID = 1
    SCALE = Dezimal("1e-18")
    NATIVE_SYMBOL = "ETH"
    ETHPLORER_BASE_URL = "https://api.ethplorer.io"

    def __init__(
        self, etherscan_client: EtherscanClient, ethplorer_client: EthplorerClient
    ):
        self._etherscan_fetcher = EtherscanFetcher(
            client=etherscan_client,
            chain_id=self.ETHERSCAN_CHAIN_ID,
            native_symbol=self.NATIVE_SYMBOL,
            scale=self.SCALE,
        )
        self._ethplorer_fetcher = EthplorerFetcher(
            client=ethplorer_client,
            base_url=self.ETHPLORER_BASE_URL,
            native_symbol=self.NATIVE_SYMBOL,
            scale=self.SCALE,
        )
        self._log = logging.getLogger(__name__)

    async def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        if ExternalIntegrationId.ETHPLORER in request.integrations:
            return await self._ethplorer_fetcher.fetch(request)
        elif ExternalIntegrationId.ETHERSCAN in request.integrations:
            try:
                return await self._etherscan_fetcher.fetch(request)
            except Exception as e:
                self._log.warning(
                    f"Etherscan fetch failed for address {request.address}: {e or type(e).__name__}. Falling back to Ethplorer."
                )

        return await self._ethplorer_fetcher.fetch(request)
