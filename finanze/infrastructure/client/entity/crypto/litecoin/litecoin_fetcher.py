import logging
from uuid import uuid4

import requests
from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from cachetools import TTLCache, cached
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

    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        balance = self._fetch_address(request.address)

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

    @cached(cache=TTLCache(maxsize=50, ttl=TTL))
    def _fetch_address(self, address: str) -> Dezimal:
        url = f"{self.BASE_URL}/{address}/balance"
        balance = self._fetch(url).get("balance", 0)

        return Dezimal(balance) * self.SCALE

    def _fetch(self, url: str) -> dict:
        try:
            response = http_get_with_backoff(
                url,
                cooldown=self.COOLDOWN,
                max_retries=self.MAX_RETRIES,
                backoff_factor=self.BACKOFF_FACTOR,
                log=self._log,
            )
        except requests.RequestException as e:
            self._log.error(f"Request error calling BlockCypher endpoint {url}: {e}")
            raise

        if response.ok:
            return response.json()

        if response.status_code == 404:
            raise AddressNotFound()
        if response.status_code == 429:
            raise TooManyRequests()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}
