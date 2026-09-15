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
from infrastructure.client.entity.crypto.litecoin.litecoin_fetcher import (
    LitecoinFetcher,
)

FAKE_ADDRESS = "ltc1qfake000000000000000000000000000000a01"


def _client_results():
    return CryptoFetchResults(
        results={
            FAKE_ADDRESS: CryptoFetchResult(
                address=FAKE_ADDRESS,
                has_txs=True,
                assets=[
                    CryptoFetchedPosition(
                        id=uuid4(),
                        symbol="LTC",
                        balance=Dezimal("4.5"),
                        type=CryptoCurrencyType.NATIVE,
                    )
                ],
            )
        }
    )


def _assert_litecoin_position(results):
    asset = results.results[FAKE_ADDRESS].assets[0]
    assert asset.symbol == "LTC"
    assert asset.balance == Dezimal("4.5")
    assert asset.chain == "litecoin"


class TestLitecoinFetcherChain:
    @pytest.mark.asyncio
    async def test_blockcypher_positions_carry_chain(self):
        fetcher = LitecoinFetcher()
        fetcher._bc_client.fetch = AsyncMock(return_value=_client_results())
        fetcher._s_client.fetch = AsyncMock()

        results = await fetcher.fetch(
            CryptoFetchRequest(integrations={}, addresses=[FAKE_ADDRESS])
        )

        _assert_litecoin_position(results)
        fetcher._s_client.fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_space_fallback_positions_carry_chain(self):
        fetcher = LitecoinFetcher()
        fetcher._bc_client.fetch = AsyncMock(side_effect=RuntimeError("down"))
        fetcher._s_client.fetch = AsyncMock(return_value=_client_results())

        results = await fetcher.fetch(
            CryptoFetchRequest(integrations={}, addresses=[FAKE_ADDRESS])
        )

        _assert_litecoin_position(results)
