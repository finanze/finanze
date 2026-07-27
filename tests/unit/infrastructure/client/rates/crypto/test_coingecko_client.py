from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from domain.dezimal import Dezimal
from infrastructure.client.rates.crypto.coingecko_client import CoinGeckoClient
from infrastructure.client.rates.crypto.crypto_dataset_client import (
    CryptoDataset,
    CryptoDatasetCoin,
    CryptoDatasetPlatform,
)


class _StubDatasetClient:
    def __init__(self, dataset):
        self._dataset = dataset

    async def load_coingecko(self):
        return self._dataset


def _dataset() -> CryptoDataset:
    coins = [
        CryptoDatasetCoin(
            id="ethereum",
            symbol="eth",
            name="Ethereum",
            icon_url=None,
            platforms={},
            prices={},
        )
    ]
    platforms = {
        "ethereum": CryptoDatasetPlatform(
            provider_id="ethereum", name="Ethereum", icon_url="https://icon.png"
        )
    }
    return CryptoDataset(
        updated_at=datetime.now(timezone.utc), coins=coins, platforms=platforms
    )


def _build_client() -> CoinGeckoClient:
    client = CoinGeckoClient(dataset_client=_StubDatasetClient(_dataset()))
    client._fetch = AsyncMock(side_effect=AssertionError("live API must not be called"))
    return client


class TestLazyCloudCache:
    @pytest.mark.asyncio
    async def test_get_asset_platforms_uses_dataset_without_initialize(self):
        client = _build_client()

        platforms = await client.get_asset_platforms()

        assert "ethereum" in platforms
        assert platforms["ethereum"].name == "Ethereum"
        client._fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_asset_lookup_uses_dataset_without_initialize(self):
        client = _build_client()

        results = await client.asset_lookup(symbol="eth")

        assert len(results) == 1
        assert results[0].symbol == "ETH"
        client._fetch.assert_not_called()


class TestGetPrices:
    @pytest.mark.asyncio
    async def test_known_symbols_are_priced_by_id(self):
        client = _build_client()
        client._fetch = AsyncMock(return_value={"ethereum": {"eur": 1701.79}})

        prices = await client.get_prices(["eth"], ["EUR"])

        assert prices == {"ETH": {"EUR": Dezimal("1701.79")}}
        params = client._fetch.await_args.kwargs["params"]
        assert params["ids"] == "ethereum"
        assert "symbols" not in params

    @pytest.mark.asyncio
    async def test_unknown_symbols_keep_the_symbols_param(self):
        client = _build_client()
        client._fetch = AsyncMock(return_value={"tok": {"eur": 1.5}})

        prices = await client.get_prices(["tok"], ["EUR"])

        assert prices == {"TOK": {"EUR": Dezimal("1.5")}}
        params = client._fetch.await_args.kwargs["params"]
        assert params["symbols"] == "tok"
        assert "ids" not in params

    @pytest.mark.asyncio
    async def test_mixed_symbols_use_both_paths(self):
        client = _build_client()
        client._fetch = AsyncMock(
            side_effect=[
                {"ethereum": {"eur": 1701.79}},
                {"tok": {"eur": 1.5}},
            ]
        )

        prices = await client.get_prices(["eth", "tok"], ["EUR"])

        assert prices == {
            "ETH": {"EUR": Dezimal("1701.79")},
            "TOK": {"EUR": Dezimal("1.5")},
        }
        used = [call.kwargs["params"] for call in client._fetch.await_args_list]
        assert used[0]["ids"] == "ethereum"
        assert used[1]["symbols"] == "tok"

    @pytest.mark.asyncio
    async def test_falls_back_to_symbols_without_dataset(self):
        client = CoinGeckoClient(dataset_client=_StubDatasetClient(None))
        client._fetch = AsyncMock(return_value={"eth": {"eur": 1701.79}})

        prices = await client.get_prices(["eth"], ["EUR"])

        assert prices == {"ETH": {"EUR": Dezimal("1701.79")}}
        assert client._fetch.await_args.kwargs["params"]["symbols"] == "eth"
