import logging
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


class LitecoinFetcher(CryptoEntityFetcher):
    TTL = 60

    BASE_URL = "https://api.blockcypher.com/v1/ltc/main/addrs"
    SCALE = Dezimal("1e-8")
    COOLDOWN = 0.2
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
                    symbol="LTC",
                    amount=balance,
                    type=CryptoCurrencyType.NATIVE,
                )
            ],
        )

    @cached(cache=Cache.MEMORY, ttl=TTL)
    async def _fetch_address(self, address: str) -> Dezimal:
        url = f"{self.BASE_URL}/{address}/balance"
        data = await self._fetch(url)
        balance = data.get("balance", 0)

        return Dezimal(balance) * self.SCALE

    async def _fetch(self, url: str) -> dict:
        try:
            response = await http_get_with_backoff(
                url,
                cooldown=self.COOLDOWN,
                max_retries=self.MAX_RETRIES,
                backoff_factor=self.BACKOFF_FACTOR,
                log=self._log,
            )
        except (httpx.RequestError, TimeoutError) as e:
            self._log.error(f"Request error calling BlockCypher endpoint {url}: {e}")
            raise

        if response.ok:
            return await response.json()

        if response.status == 404:
            raise AddressNotFound()
        if response.status == 429:
            raise TooManyRequests()

        body = await response.text()
        self._log.error("Error Response Body:" + body)
        response.raise_for_status()
        return {}
