import logging
from urllib.parse import quote
from uuid import uuid4

import requests
import time

from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from cachetools import TTLCache, cached
from domain.crypto import CryptoFetchRequest
from domain.dezimal import Dezimal
from domain.exception.exceptions import AddressNotFound, TooManyRequests
from domain.global_position import (
    CryptoCurrency,
    CryptoCurrencyWallet,
)
from requests import Response


class BitcoinFetcher(CryptoEntityFetcher):
    TTL = 60

    BASE_URL = "https://blockchain.info"
    SCALE = Dezimal("1e-8")
    COOLDOWN = 0.25

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

    def fetch_multiple(
        self, requests: list[CryptoFetchRequest]
    ) -> list[CryptoCurrencyWallet]:
        if not requests:
            return []

        addresses = [r.address for r in requests]
        data = self._fetch_multiaddr(addresses)

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
                    id=uuid4(),
                    wallet_connection_id=req.connection_id,
                    symbol="BTC",
                    crypto=CryptoCurrency.BITCOIN,
                    amount=amount,
                )
            )

        return wallets

    def _fetch_multiaddr(self, addresses: list[str]) -> dict:
        active = "|".join(addresses)
        active_enc = quote(active, safe="")
        url = f"{self.BASE_URL}/multiaddr?active={active_enc}"

        return self._fetch(url).json()

    @cached(cache=TTLCache(maxsize=50, ttl=TTL))
    def _fetch_address(self, address: str) -> Dezimal:
        url = f"{self.BASE_URL}/q/addressbalance/{address}"
        text = self._fetch(url).text

        return Dezimal(text) * self.SCALE

    def _fetch(self, url: str) -> Response:
        response = requests.get(url)
        time.sleep(self.COOLDOWN)
        if response.ok:
            return response

        if response.status_code == 404:
            raise AddressNotFound()

        elif response.status_code == 429:
            raise TooManyRequests()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return response
