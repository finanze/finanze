import logging
from uuid import uuid4

from domain.crypto import CryptoFetchRequest
from domain.dezimal import Dezimal
from domain.global_position import (
    CryptoCurrencyPosition,
    CryptoCurrencyType,
    CryptoCurrencyWallet,
)
from infrastructure.client.crypto.ethplorer.ethplorer_client import EthplorerClient


class EthplorerFetcher:
    TTL = 60
    DEFAULT_API_KEY = "freekey"
    COOLDOWN = 0.4
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 0.5

    def __init__(
        self,
        client: EthplorerClient,
        base_url: str,
        native_symbol: str,
        scale: Dezimal,
    ):
        self._ethplorer_client = client

        self.base_url = base_url
        self.native_symbol = native_symbol
        self.scale = scale

        self._log = logging.getLogger(__name__)

    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        data = self._ethplorer_client.fetch_address_info(self.base_url, request.address)

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
