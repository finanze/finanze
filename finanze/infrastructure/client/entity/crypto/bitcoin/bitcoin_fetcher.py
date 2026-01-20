import logging
from urllib.parse import quote
from uuid import uuid4

import httpx

from aiocache import cached, Cache
from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from domain.crypto import CryptoFetchRequest, CryptoCurrencyType
from domain.dezimal import Dezimal
from domain.exception.exceptions import AddressNotFound, TooManyRequests
from domain.global_position import (
    CryptoCurrencyPosition,
    CryptoCurrencyWallet,
)
from infrastructure.client.http.backoff import http_get_with_backoff
from infrastructure.client.http.http_response import HttpResponse


class BitcoinFetcher(CryptoEntityFetcher):
    TTL = 60

    BASE_URL = "https://blockchain.info"
    SCALE = Dezimal("1e-8")
    COOLDOWN = 0.4
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 0.5

    def __init__(self):
        self._log = logging.getLogger(__name__)

    async def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        balance = await self._fetch_address(request.address)

        return CryptoCurrencyWallet(
            id=request.connection_id,
            assets=[
                CryptoCurrencyPosition(
                    id=uuid4(),
                    symbol="BTC",
                    amount=balance,
                    type=CryptoCurrencyType.NATIVE,
                )
            ],
        )

    async def fetch_multiple(
        self, requests: list[CryptoFetchRequest]
    ) -> list[CryptoCurrencyWallet]:
        if not requests:
            return []

        addresses = [r.address for r in requests]
        data = await self._fetch_multiaddr(addresses)

        balances_map = {}
        for addr_info in data.get("addresses", []):
            addr = addr_info.get("address")
            final_balance = addr_info.get("final_balance", 0)
            try:
                balances_map[addr] = Dezimal(final_balance) * self.SCALE
            except Exception:
                balances_map[addr] = Dezimal(0)

        wallets = []
        for req in requests:
            amount = balances_map.get(req.address, Dezimal(0))
            wallets.append(
                CryptoCurrencyWallet(
                    id=req.connection_id,
                    assets=[
                        CryptoCurrencyPosition(
                            id=uuid4(),
                            symbol="BTC",
                            amount=amount,
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            )

        return wallets

    async def _fetch_multiaddr(self, addresses: list[str]) -> dict:
        active = "|".join(addresses)
        active_enc = quote(active, safe="")
        url = f"{self.BASE_URL}/multiaddr?active={active_enc}"

        resp = await self._fetch(url)
        return await resp.json()

    @cached(cache=Cache.MEMORY, ttl=TTL)
    async def _fetch_address(self, address: str) -> Dezimal:
        url = f"{self.BASE_URL}/q/addressbalance/{address}"
        resp = await self._fetch(url)
        text = await resp.text()

        return Dezimal(text) * self.SCALE

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
