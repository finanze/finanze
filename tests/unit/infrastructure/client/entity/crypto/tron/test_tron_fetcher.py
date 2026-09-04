from unittest.mock import AsyncMock

import pytest

from domain.crypto import CryptoCurrencyType, CryptoFetchRequest
from domain.dezimal import Dezimal
from infrastructure.client.entity.crypto.tron.tron_fetcher import TronFetcher

FAKE_ADDRESS = "TFAKE000000000000000000000000000A01"
TOKEN_CONTRACT = "TFAKETOKEN0000000000000000000000A02"


def _account_payload():
    return {
        "balance": "1500000",
        "trc20token_balances": [
            {
                "tokenAbbr": "USDT",
                "tokenId": TOKEN_CONTRACT,
                "tokenName": "Fake Tether",
                "tokenDecimal": "6",
                "balance": "2500000",
            }
        ],
    }


class TestTronFetcherChain:
    @pytest.mark.asyncio
    async def test_positions_carry_chain(self):
        fetcher = TronFetcher()
        fetcher._fetch_account_info = AsyncMock(return_value=_account_payload())

        results = await fetcher.fetch(
            CryptoFetchRequest(integrations={}, addresses=[FAKE_ADDRESS])
        )

        by_type = {a.type: a for a in results.results[FAKE_ADDRESS].assets}
        native = by_type[CryptoCurrencyType.NATIVE]
        token = by_type[CryptoCurrencyType.TOKEN]

        assert native.symbol == "TRX"
        assert native.balance == Dezimal("1.5")
        assert native.chain == "tron"

        assert token.symbol == "USDT"
        assert token.contract_address == TOKEN_CONTRACT.lower()
        assert token.balance == Dezimal("2.5")
        assert token.chain == "tron"
