from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from domain.crypto import (
    CryptoCurrencyType,
    CryptoFetchedPosition,
    CryptoFetchRequest,
    CryptoFetchResult,
    CryptoFetchResults,
)
from domain.dezimal import Dezimal
from infrastructure.client.entity.crypto.bitcoin.bitcoin_fetcher import BitcoinFetcher

FAKE_ADDRESS = "bc1qfake0000000000000000000000000000000a01"
EMPTY_ADDRESS = "bc1qfake0000000000000000000000000000000a02"


def _client_results():
    return CryptoFetchResults(
        results={
            FAKE_ADDRESS: CryptoFetchResult(
                address=FAKE_ADDRESS,
                has_txs=True,
                assets=[
                    CryptoFetchedPosition(
                        id=uuid4(),
                        symbol="BTC",
                        balance=Dezimal("0.25"),
                        type=CryptoCurrencyType.NATIVE,
                    )
                ],
            ),
            EMPTY_ADDRESS: None,
        }
    )


class TestBitcoinFetcherChain:
    @pytest.mark.asyncio
    async def test_positions_carry_chain(self):
        fetcher = BitcoinFetcher()
        fetcher._bc_client.fetch = AsyncMock(return_value=_client_results())

        results = await fetcher.fetch(
            CryptoFetchRequest(integrations={}, addresses=[FAKE_ADDRESS, EMPTY_ADDRESS])
        )

        asset = results.results[FAKE_ADDRESS].assets[0]
        assert asset.symbol == "BTC"
        assert asset.balance == Dezimal("0.25")
        assert asset.chain == "bitcoin"
        assert results.results[EMPTY_ADDRESS] is None
