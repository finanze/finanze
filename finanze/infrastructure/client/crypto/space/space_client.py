import logging
from uuid import uuid4

import httpx
from aiocache import cached, Cache

from domain.crypto import (
    CryptoFetchRequest,
    CryptoCurrencyType,
    CryptoFetchResults,
    CryptoFetchResult,
    CryptoFetchedPosition,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import TooManyRequests
from infrastructure.client.http.backoff import http_get_with_backoff


class SpaceClient:
    TTL = 60

    COOLDOWN = 0.5
    MAX_RETRIES = 5
    BACKOFF_EXPONENT_BASE = 2.5
    BACKOFF_FACTOR = 0.6

    CHAIN_URL = {
        "ltc": "https://litecoinspace.org/api",
        "btc": "https://mempool.space/api",
    }

    def __init__(self, chain: str, symbol: str, scale: Dezimal):
        self.chain = chain
        self.symbol = symbol
        self.scale = scale
        self.base_url = self.CHAIN_URL[chain]
        self._log = logging.getLogger(__name__)

    async def fetch(self, request: CryptoFetchRequest) -> CryptoFetchResults:
        results: dict[str, CryptoFetchResult | None] = {}

        for address in request.addresses:
            per_address = await self._fetch_address(address, results)
            if per_address is not None:
                results[address] = per_address

        return CryptoFetchResults(results=results)

    @cached(
        cache=Cache.MEMORY,
        ttl=TTL,
        key_builder=lambda f,
        self,
        address,
        fetched_results: f"space_address_{address}",
    )
    async def _fetch_address(
        self, address: str, fetched_results: dict[str, CryptoFetchResult | None]
    ) -> CryptoFetchResult | None:
        url = f"{self.base_url}/address/{address}"
        data = await self._fetch(url, fetched_results)
        if data is None:
            return None

        chain_stats = data.get("chain_stats")
        balance = Dezimal(chain_stats.get("funded_txo_sum", 0)) * self.scale
        return CryptoFetchResult(
            address=address,
            has_txs=chain_stats.get("tx_count", 0) > 0,
            assets=[
                CryptoFetchedPosition(
                    id=uuid4(),
                    symbol=self.symbol,
                    balance=balance,
                    type=CryptoCurrencyType.NATIVE,
                )
            ],
        )

    async def _fetch(self, url: str, fetched_results) -> dict | None:
        try:
            response = await http_get_with_backoff(
                url,
                cooldown=self.COOLDOWN,
                max_retries=self.MAX_RETRIES,
                backoff_exponent_base=self.BACKOFF_EXPONENT_BASE,
                backoff_factor=self.BACKOFF_FACTOR,
                log=self._log,
            )
        except (httpx.RequestError, TimeoutError) as e:
            self._log.error(f"Request error calling Space endpoint {url}: {e}")
            raise

        if response.ok:
            return await response.json()

        if response.status == 400:
            return None

        if response.status == 429:
            raise TooManyRequests(CryptoFetchResults(fetched_results))

        body = await response.text()
        self._log.error("Error Response Body:" + body)
        response.raise_for_status()
        return None
