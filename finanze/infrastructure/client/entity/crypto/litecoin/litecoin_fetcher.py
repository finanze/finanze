import logging

from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from domain.crypto import (
    CryptoFetchRequest,
    CryptoFetchResults,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import TooManyRequests
from infrastructure.client.crypto.blockcypher.blockcypher_client import (
    BlockcypherClient,
)
from infrastructure.client.crypto.space.space_client import SpaceClient


class LitecoinFetcher(CryptoEntityFetcher):
    TTL = 60
    SCALE = Dezimal("1e-8")

    def __init__(self):
        self._bc_client = BlockcypherClient(chain="ltc", symbol="LTC", scale=self.SCALE)
        self._s_client = SpaceClient(chain="ltc", symbol="LTC", scale=self.SCALE)

        self._log = logging.getLogger(__name__)

    async def fetch(self, request: CryptoFetchRequest) -> CryptoFetchResults:
        results: CryptoFetchResults | None = None

        try:
            return await self._bc_client.fetch(request)
        except Exception as e:
            if isinstance(e, TooManyRequests):
                results = e.completed
                self._log.warning("Rate limit hit for Litecoin Blockcypher API")
            else:
                self._log.error(f"Error fetching from Blockcypher for Litecoin: {e}")

        if not results:
            results = CryptoFetchResults(results={})

        remaining_addresses = (
            [addr for addr in request.addresses if addr not in results.results]
            if results
            else request.addresses
        )

        request = CryptoFetchRequest(
            integrations=request.integrations,
            addresses=remaining_addresses,
            txs=request.txs,
        )
        results += await self._s_client.fetch(request)

        return results
