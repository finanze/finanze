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
    CryptoCurrencyToken,
    CryptoCurrencyWallet,
    CryptoToken,
)


class TronFetcher(CryptoEntityFetcher):
    TTL = 60
    BASE_URL = "https://apilist.tronscan.org/api/account"
    TRX_SCALE = Dezimal("1e-6")
    COOLDOWN = 0.2

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        data = self._fetch_account_info(request.address)

        if not data or "balance" not in data:
            raise AddressNotFound()

        trx_balance = Dezimal(data.get("balance", "0")) * self.TRX_SCALE

        tokens = self._parse_tokens(data)

        return CryptoCurrencyWallet(
            id=uuid4(),
            wallet_connection_id=request.connection_id,
            symbol="TRX",
            crypto=CryptoCurrency.TRON,
            amount=trx_balance,
            tokens=tokens,
        )

    def _parse_tokens(self, data: dict) -> list[CryptoCurrencyToken]:
        tokens = []
        if "trc20token_balances" not in data:
            return tokens

        for token_data in data["trc20token_balances"]:
            symbol = token_data.get("tokenAbbr")
            if not symbol:
                continue

            try:
                token_enum = CryptoToken(symbol)
            except (ValueError, TypeError):
                self._log.debug(f"Token {symbol} not supported. Skipping.")
                continue

            try:
                decimals = int(token_data.get("tokenDecimal", 0))
                balance = Dezimal(token_data.get("balance", "0"))
                amount = balance * Dezimal(f"1e-{decimals}")
            except (ValueError, TypeError):
                self._log.warning(f"Could not parse amount for token {symbol}")
                continue

            tokens.append(
                CryptoCurrencyToken(
                    id=uuid4(),
                    token_id=token_data.get("tokenId"),
                    name=token_data.get("tokenName"),
                    symbol=symbol,
                    token=token_enum,
                    amount=amount,
                    type=token_data.get("tokenType"),
                )
            )
        return tokens

    @cached(cache=TTLCache(maxsize=50, ttl=TTL))
    def _fetch_account_info(self, address: str) -> dict:
        url = f"{self.BASE_URL}?address={address}"
        return self._fetch(url)

    def _fetch(self, url: str) -> dict:
        response = requests.get(url)

        time.sleep(self.COOLDOWN)

        if not response.ok:
            if response.status_code == 429:
                raise TooManyRequests()

            self._log.error(
                f"Error fetching from Tronscan: {response.status_code} {response.text}"
            )
            response.raise_for_status()

        return response.json()
