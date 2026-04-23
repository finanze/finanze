import logging
from urllib.parse import quote
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
from domain.exception.exceptions import AddressNotFound, TooManyRequests
from infrastructure.client.http.backoff import http_get_with_backoff
from infrastructure.client.http.http_response import HttpResponse


class BlockchainClient:
    TTL = 60

    BASE_URL = "https://blockchain.info"
    COOLDOWN = 0.4
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 0.5

    MAX_ADDRESSES_PER_REQUEST = 80

    def __init__(self, scale: Dezimal):
        self.scale = scale
        self._log = logging.getLogger(__name__)

    async def fetch(self, request: CryptoFetchRequest) -> CryptoFetchResults:
        results: dict[str, CryptoFetchResult | None] = {}
        txs_number = 1 if request.txs else 0

        for i in range(0, len(request.addresses), self.MAX_ADDRESSES_PER_REQUEST):
            batch = request.addresses[i : i + self.MAX_ADDRESSES_PER_REQUEST]
            data = await self._fetch_multiaddr(batch, txs_number)

            for addr_info in data.get("addresses", []):
                addr = addr_info.get("address")
                final_balance = addr_info.get("final_balance", 0)
                tx_amount = addr_info.get("n_tx", 0)
                try:
                    balance = Dezimal(final_balance) * self.scale
                except Exception:
                    self._log.error(
                        f"Error parsing balance for address {addr}: {final_balance}"
                    )
                    balance = Dezimal(0)

                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=bool(tx_amount),
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=balance,
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )

        return CryptoFetchResults(results=results)

    async def _fetch_multiaddr(self, addresses: list[str], txs: int = 0) -> dict:
        active = "|".join(addresses)
        active_enc = quote(active, safe="")
        url = f"{self.BASE_URL}/multiaddr?active={active_enc}&n={txs}"

        resp = await self._fetch(url)
        return await resp.json()

    @cached(cache=Cache.MEMORY, ttl=TTL)
    async def _fetch_address(self, address: str) -> Dezimal:
        url = f"{self.BASE_URL}/q/addressbalance/{address}"
        resp = await self._fetch(url)
        text = await resp.text()

        return Dezimal(text) * self.scale

    async def _fetch(self, url: str) -> HttpResponse:
        try:
            response = await http_get_with_backoff(
                url,
                cooldown=self.COOLDOWN,
                max_retries=self.MAX_RETRIES,
                backoff_factor=self.BACKOFF_FACTOR,
                log=self._log,
            )
        except (httpx.RequestError, TimeoutError) as e:
            self._log.error(
                f"Request error calling blockchain.info endpoint {url}: {e}"
            )
            raise

        if response.ok:
            return response

        if response.status == 404:
            raise AddressNotFound()
        if response.status == 429:
            raise TooManyRequests()

        body = await response.text()
        self._log.error("Error Response Body:" + body)
        response.raise_for_status()
        return response
