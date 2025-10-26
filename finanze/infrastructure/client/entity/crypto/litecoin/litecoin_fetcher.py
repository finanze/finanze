import logging
import time
from uuid import uuid4

import requests
from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from cachetools import TTLCache, cached
from domain.crypto import CryptoFetchRequest
from domain.dezimal import Dezimal
from domain.exception.exceptions import AddressNotFound, TooManyRequests
from domain.global_position import (
    CryptoCurrency,
    CryptoCurrencyWallet,
)


class LitecoinFetcher(CryptoEntityFetcher):
    TTL = 60

    BASE_URL = "https://api.blockcypher.com/v1/ltc/main/addrs"
    SCALE = Dezimal("1e-8")
    COOLDOWN = 0.2

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        balance = self._fetch_address(request.address)

        return CryptoCurrencyWallet(
            id=uuid4(),
            wallet_connection_id=request.connection_id,
            symbol="LTC",
            crypto=CryptoCurrency.LITECOIN,
            amount=balance,
        )

    @cached(cache=TTLCache(maxsize=50, ttl=TTL))
    def _fetch_address(self, address: str) -> Dezimal:
        url = f"{self.BASE_URL}/{address}/balance"
        balance = self._fetch(url)["balance"]

        return Dezimal(balance) * self.SCALE

    def _fetch(self, url: str) -> dict:
        response = requests.get(url)
        time.sleep(self.COOLDOWN)
        if response.ok:
            return response.json()

        if response.status_code == 404:
            raise AddressNotFound()

        elif response.status_code == 429:
            raise TooManyRequests()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}
