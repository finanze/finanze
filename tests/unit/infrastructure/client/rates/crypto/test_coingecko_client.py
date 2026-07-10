from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

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
