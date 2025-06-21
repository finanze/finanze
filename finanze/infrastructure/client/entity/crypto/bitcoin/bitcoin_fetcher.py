import logging
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


class BitcoinFetcher(CryptoEntityFetcher):
    TTL = 60

    BASE_URL = "https://blockchain.info/q/addressbalance"
    SCALE = Dezimal("1e-8")

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        balance = self._fetch_address(request.address)

        return CryptoCurrencyWallet(
            id=uuid4(),
            wallet_connection_id=request.connection_id,
            symbol="BTC",
            crypto=CryptoCurrency.BITCOIN,
            amount=balance,
        )

    @cached(cache=TTLCache(maxsize=50, ttl=TTL))
    def _fetch_address(self, address: str) -> Dezimal:
        url = f"{self.BASE_URL}/{address}"
        text = self._fetch(url)

        return Dezimal(text) * self.SCALE

    def _fetch(self, url: str) -> str:
        response = requests.get(url)
        if response.ok:
            return response.text

        if response.status_code == 404:
            raise AddressNotFound()

        elif response.status_code == 429:
            raise TooManyRequests()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return ""
