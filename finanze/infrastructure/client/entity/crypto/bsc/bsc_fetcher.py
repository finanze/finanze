import logging

from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from domain.crypto import CryptoFetchRequest
from domain.dezimal import Dezimal
from domain.global_position import (
    CryptoCurrencyWallet,
)
from infrastructure.client.crypto.etherscan.etherscan_client import EtherscanClient
from infrastructure.client.crypto.etherscan.etherscan_fetcher import EtherscanFetcher
from infrastructure.client.crypto.etherscan.ethplorer_fetcher import EthplorerFetcher


class BSCFetcher(CryptoEntityFetcher):
    ETHERSCAN_CHAIN_ID = 56
    SCALE = Dezimal("1e-18")
    NATIVE_SYMBOL = "BNB"
    ETHPLORER_BASE_URL = "https://api.binplorer.com"

    def __init__(self, etherscan_client: EtherscanClient):
        self._etherscan_fetcher = EtherscanFetcher(
            etherscan_client, self.ETHERSCAN_CHAIN_ID, self.SCALE, self.NATIVE_SYMBOL
        )
        self._binplorer_fetcher = EthplorerFetcher(
            base_url=self.ETHPLORER_BASE_URL,
            native_symbol=self.NATIVE_SYMBOL,
            scale=self.SCALE,
        )

        self._log = logging.getLogger(__name__)

    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        if request.integrations.ethplorer:
            return self._binplorer_fetcher.fetch(request)
        elif request.integrations.etherscan:
            try:
                return self._etherscan_fetcher.fetch(request)
            except Exception as e:
                self._log.warning(
                    f"Etherscan fetch failed for address {request.address}: {e}. Falling back to Ethplorer."
                )

        return self._binplorer_fetcher.fetch(request)
