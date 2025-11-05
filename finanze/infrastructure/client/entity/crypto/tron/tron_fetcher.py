import logging
from uuid import uuid4

import requests
from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from cachetools import TTLCache, cached
from domain.crypto import CryptoFetchRequest
from domain.dezimal import Dezimal
from domain.exception.exceptions import AddressNotFound, TooManyRequests
from domain.global_position import (
    CryptoCurrencyPosition,
    CryptoCurrencyType,
    CryptoCurrencyWallet,
)
from infrastructure.client.http.backoff import http_get_with_backoff


class TronFetcher(CryptoEntityFetcher):
    TTL = 60
    BASE_URL = "https://apilist.tronscan.org/api/account"
    TRX_SCALE = Dezimal("1e-6")
    COOLDOWN = 0.2
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 0.5

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        data = self._fetch_account_info(request.address)

        if not data or "balance" not in data:
            raise AddressNotFound()

        trx_balance = Dezimal(data.get("balance", "0")) * self.TRX_SCALE

        assets = [
            CryptoCurrencyPosition(
                id=uuid4(),
                symbol="TRX",
                amount=trx_balance,
                type=CryptoCurrencyType.NATIVE,
            )
        ]
        assets += self._parse_tokens(data)

        return CryptoCurrencyWallet(
            id=request.connection_id,
            assets=assets,
        )

    def _parse_tokens(self, data: dict) -> list[CryptoCurrencyPosition]:
        tokens = []
        if "trc20token_balances" not in data:
            return tokens

        for token_data in data["trc20token_balances"]:
            symbol = token_data.get("tokenAbbr")
            if not symbol:
                continue

            try:
                decimals = int(token_data.get("tokenDecimal", 0))
                balance = Dezimal(token_data.get("balance", "0"))
                amount = balance * Dezimal(f"1e-{decimals}")
            except (ValueError, TypeError):
                self._log.warning(f"Could not parse amount for token {symbol}")
                continue

            tokens.append(
                CryptoCurrencyPosition(
                    id=uuid4(),
                    contract_address=token_data.get("tokenId"),
                    name=token_data.get("tokenName"),
                    symbol=symbol,
                    amount=amount,
                    type=CryptoCurrencyType.TOKEN,
                )
            )
        return tokens

    @cached(cache=TTLCache(maxsize=50, ttl=TTL))
    def _fetch_account_info(self, address: str) -> dict:
        url = f"{self.BASE_URL}?address={address}"
        return self._fetch(url)

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
            self._log.error(f"Request error calling Tronscan endpoint {url}: {e}")
            raise

        if not response.ok:
            if response.status_code == 429:
                raise TooManyRequests()

            self._log.error(
                f"Error fetching from Tronscan: {response.status_code} {response.text}"
            )
            response.raise_for_status()

        return response.json()
