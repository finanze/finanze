import logging

from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from domain.crypto import (
    CryptoFetchRequest,
    CryptoFetchResults,
)
from domain.dezimal import Dezimal
from infrastructure.client.crypto.blockchain.blockchain_client import BlockchainClient

# Zerion chain id, so positions from both providers share a grouping key.
CHAIN = "bitcoin"


def _set_chain(results: CryptoFetchResults) -> CryptoFetchResults:
    for result in results.results.values():
        if result is None:
            continue
        for asset in result.assets:
            asset.chain = CHAIN
    return results


class BitcoinFetcher(CryptoEntityFetcher):
    SCALE = Dezimal("1e-8")

    def __init__(self):
        self._bc_client = BlockchainClient(self.SCALE)
        # self._bstr_client = BlockstreamClient(self.SCALE)
        # self._mps_client = SpaceClient("btc", "BTC", self.SCALE)
        self._log = logging.getLogger(__name__)

    async def fetch(self, request: CryptoFetchRequest) -> CryptoFetchResults:
        return _set_chain(await self._bc_client.fetch(request))
