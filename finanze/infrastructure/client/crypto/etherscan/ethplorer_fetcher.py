import logging
from typing import Optional
from uuid import uuid4

import requests
from application.ports.connectable_integration import ConnectableIntegration
from cachetools import TTLCache, cached
from domain.crypto import CryptoFetchRequest
from domain.dezimal import Dezimal
from domain.exception.exceptions import AddressNotFound, TooManyRequests
from domain.external_integration import (
    EtherscanIntegrationData,
    EthplorerIntegrationData,
)
from domain.global_position import (
    CryptoCurrencyPosition,
    CryptoCurrencyType,
    CryptoCurrencyWallet,
)
from infrastructure.client.http.backoff import http_get_with_backoff


class EthplorerFetcher(ConnectableIntegration[EthplorerIntegrationData]):
    TTL = 60
    DEFAULT_API_KEY = "freekey"
    COOLDOWN = 0.4
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 0.5

    def __init__(self, base_url: str, native_symbol: str, scale: Dezimal):
        self.base_url = base_url
        self.native_symbol = native_symbol
        self.scale = scale
        self._log = logging.getLogger(__name__)

    def setup(self, credentials: EthplorerIntegrationData):
        url = f"{self.base_url}/getLastBlock?apiKey={self._get_api_key(credentials)}"
        self._fetch(url)

    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        data = self._fetch_address_info(request.address)

        eth_balance = Dezimal(data["ETH"]["rawBalance"]) * self.scale

        assets = [
            CryptoCurrencyPosition(
                id=uuid4(),
                symbol=self.native_symbol,
                amount=eth_balance,
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
        if "tokens" not in data:
            return tokens

        for token_data in data["tokens"]:
            token_info = token_data.get("tokenInfo")
            if not token_info:
                continue

            symbol = token_info.get("symbol")

            try:
                decimals = int(token_info.get("decimals", 0))
                balance = Dezimal(token_data.get("balance", 0))
                amount = balance * Dezimal(f"1e-{decimals}")
            except (ValueError, TypeError):
                self._log.warning(f"Could not parse amount for token {symbol}")
                continue

            tokens.append(
                CryptoCurrencyPosition(
                    id=uuid4(),
                    contract_address=token_info.get("address", "").lower(),
                    name=token_info.get("name"),
                    symbol=symbol,
                    amount=amount,
                    type=CryptoCurrencyType.TOKEN,
                )
            )
        return tokens

    @cached(cache=TTLCache(maxsize=50, ttl=TTL))
    def _fetch_address_info(
        self,
        address: str,
        credentials: Optional[EtherscanIntegrationData] = None,
    ) -> dict:
        url = f"{self.base_url}/getAddressInfo/{address}?apiKey={self._get_api_key(credentials)}"
        return self._fetch(url)

    def _get_api_key(
        self, credentials: Optional[EtherscanIntegrationData] = None
    ) -> str:
        if credentials and credentials.api_key:
            return credentials.api_key
        return self.DEFAULT_API_KEY

    def _fetch(
        self,
        url: str,
    ) -> dict:
        try:
            response = http_get_with_backoff(
                url,
                cooldown=self.COOLDOWN,
                max_retries=self.MAX_RETRIES,
                backoff_factor=self.BACKOFF_FACTOR,
                log=self._log,
            )
        except requests.RequestException as e:
            self._log.error(f"Request error calling Ethplorer endpoint {url}: {e}")
            raise

        if not response.ok:
            if response.status_code == 429:
                raise TooManyRequests()

            self._log.error(
                f"Error fetching from Ethplorer: {response.status_code} {response.text}"
            )
            response.raise_for_status()

        data = response.json()
        if "error" in data:
            error = data["error"]
            self._log.error(f"Ethplorer API error: {error}")
            if error.get("code") == 150:
                raise AddressNotFound()
            raise Exception(f"Ethplorer API error: {error.get('message')}")

        return data
