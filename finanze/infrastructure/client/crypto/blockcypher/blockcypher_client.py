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


class BlockcypherClient:
    TTL = 60

    URL = "https://api.blockcypher.com/v1/"
    COOLDOWN = 0.5
    MAX_RETRIES = 5
    BACKOFF_EXPONENT_BASE = 2.5
    BACKOFF_FACTOR = 0.6

    MAX_ADDRESSES_PER_REQUEST = 2

    def __init__(self, chain: str, symbol: str, scale: Dezimal):
        self.chain = chain
        self.symbol = symbol
        self.scale = scale
        self.base_url = f"{self.URL}{self.chain}"
        self._log = logging.getLogger(__name__)

    async def fetch(self, request: CryptoFetchRequest) -> CryptoFetchResults:
        results: dict[str, CryptoFetchResult | None] = {}

        for i in range(0, len(request.addresses), self.MAX_ADDRESSES_PER_REQUEST):
            batch = request.addresses[i : i + self.MAX_ADDRESSES_PER_REQUEST]
            per_address = await self._fetch_addresses(batch, results)
            results.update(per_address)

        return CryptoFetchResults(results=results)

    @cached(
        cache=Cache.MEMORY,
        ttl=TTL,
        key_builder=lambda f, self, addresses, fetched_results: (
            f"blockcypher_addresses_{'_'.join(addresses)}"
        ),
    )
    async def _fetch_addresses(
        self, addresses: list[str], fetched_results: dict[str, CryptoFetchResult | None]
    ) -> dict[str, CryptoFetchResult | None]:
        if len(addresses) > self.MAX_ADDRESSES_PER_REQUEST:
            raise ValueError(
                f"Maximum {self.MAX_ADDRESSES_PER_REQUEST} addresses allowed per request"
            )

        addresses_param = ";".join(addresses) if len(addresses) > 1 else addresses[0]

        url = f"{self.base_url}/main/addrs/{addresses_param}/balance?omitWalletAddresses=true"
        data = await self._fetch(url, fetched_results)

        items = data if isinstance(data, list) else [data]
        results: dict[str, CryptoFetchResult | None] = {
            addr: None for addr in addresses
        }

        for item in items:
            if "error" in item:
                continue

            addr = item.get("address")
            balance = Dezimal(item.get("balance", 0)) * self.scale
            tx_amount = item.get("n_tx", 0)
            results[addr] = CryptoFetchResult(
                address=addr,
                has_txs=bool(tx_amount),
                assets=[
                    CryptoFetchedPosition(
                        id=uuid4(),
                        symbol=self.symbol,
                        balance=balance,
                        type=CryptoCurrencyType.NATIVE,
                    )
                ],
            )

        return results

    async def _fetch(self, url: str, fetched_results) -> dict | list | None:
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
            self._log.error(f"Request error calling BlockCypher endpoint {url}: {e}")
            raise

        if response.ok or response.status == 404:
            return await response.json()

        if response.status == 429:
            raise TooManyRequests(CryptoFetchResults(fetched_results))

        body = await response.text()
        self._log.error("Error Response Body:" + body)
        response.raise_for_status()
        return None
