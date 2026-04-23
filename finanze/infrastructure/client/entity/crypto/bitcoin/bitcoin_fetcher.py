import logging

from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from domain.crypto import (
    CryptoFetchRequest,
    CryptoFetchResults,
)
from domain.dezimal import Dezimal
from infrastructure.client.crypto.blockchain.blockchain_client import BlockchainClient


class BitcoinFetcher(CryptoEntityFetcher):
    SCALE = Dezimal("1e-8")

    def __init__(self):
        self._bc_client = BlockchainClient(self.SCALE)
        # self._bstr_client = BlockstreamClient(self.SCALE)
        # self._mps_client = SpaceClient("btc", "BTC", self.SCALE)
        self._log = logging.getLogger(__name__)

    async def fetch(self, request: CryptoFetchRequest) -> CryptoFetchResults:
        return await self._bc_client.fetch(request)
