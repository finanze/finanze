from datetime import datetime, timezone

import pytest

from domain.dezimal import Dezimal
from domain.crypto import CryptoCurrencyType
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.rates.crypto.coinmarketcap_dataset_client import (
    CoinMarketCapDatasetClient,
)
from infrastructure.client.rates.crypto.crypto_dataset_client import (
    CryptoDataset,
    CryptoDatasetCoin,
    CryptoDatasetPlatform,
)


def _dataset() -> CryptoDataset:
    coins = [
        CryptoDatasetCoin(
            id="1",
            symbol="BTC",
            name="Bitcoin",
            icon_url="https://icons/1.png",
            platforms={},
            prices={"USD": Dezimal("64661.21"), "EUR": Dezimal("56575.39")},
        ),
        CryptoDatasetCoin(
            id="1027",
            symbol="ETH",
            name="Ethereum",
            icon_url="https://icons/1027.png",
            platforms={"ethereum": "0xToken"},
            prices={"EUR": Dezimal("2700")},
        ),
    ]
    platforms = {
        "ethereum": CryptoDatasetPlatform(
            provider_id="ethereum", name="Ethereum", icon_url=None
        )
    }
    return CryptoDataset(
        updated_at=datetime.now(timezone.utc), coins=coins, platforms=platforms
    )


class _StubDatasetClient:
    def __init__(self, dataset):
        self._dataset = dataset

    async def load_coinmarketcap(self, max_age=None, **kwargs):
        return self._dataset


def _client(dataset=None) -> CoinMarketCapDatasetClient:
    return CoinMarketCapDatasetClient(_StubDatasetClient(dataset))


class TestCoinMarketCapDatasetClient:
    @pytest.mark.asyncio
    async def test_search_by_symbol(self):
        client = _client(_dataset())

        results = await client.search("btc")

        assert len(results) == 1
        asset = results[0]
        assert asset.symbol == "BTC"
        assert asset.external_ids == {ExternalIntegrationId.COINMARKETCAP.value: "1"}
        assert asset.icon_urls == ["https://icons/1.png"]

    @pytest.mark.asyncio
    async def test_get_prices_by_symbol(self):
        client = _client(_dataset())

        prices = await client.get_prices(["ETH"], ["EUR", "USD"])

        assert prices == {"ETH": {"EUR": Dezimal("2700")}}

    @pytest.mark.asyncio
    async def test_get_prices_by_addresses(self):
        client = _client(_dataset())

        prices = await client.get_prices_by_addresses(["0xTOKEN"], ["EUR"])

        assert prices == {"0xtoken": {"EUR": Dezimal("2700")}}

    @pytest.mark.asyncio
    async def test_asset_lookup_builds_platforms(self):
        client = _client(_dataset())

        results = await client.asset_lookup(symbol="eth")

        assert len(results) == 1
        asset = results[0]
        assert asset.provider == ExternalIntegrationId.COINMARKETCAP
        assert asset.provider_id == "1027"
        assert len(asset.platforms) == 1
        assert asset.platforms[0].contract_address == "0xToken"

    @pytest.mark.asyncio
    async def test_get_asset_platforms(self):
        client = _client(_dataset())

        platforms = await client.get_asset_platforms()

        assert "ethereum" in platforms
        assert platforms["ethereum"].name == "Ethereum"

    @pytest.mark.asyncio
    async def test_get_asset_details_native(self):
        client = _client(_dataset())

        details = await client.get_asset_details("1", ["EUR", "USD"])

        assert details is not None
        assert details.provider == ExternalIntegrationId.COINMARKETCAP
        assert details.provider_id == "1"
        assert details.symbol == "BTC"
        assert details.type == CryptoCurrencyType.NATIVE
        assert details.platforms == []
        assert details.price == {
            "EUR": Dezimal("56575.39"),
            "USD": Dezimal("64661.21"),
        }

    @pytest.mark.asyncio
    async def test_get_asset_details_token(self):
        client = _client(_dataset())

        details = await client.get_asset_details("1027", ["EUR"])

        assert details is not None
        assert details.type == CryptoCurrencyType.TOKEN
        assert len(details.platforms) == 1
        assert details.platforms[0].contract_address == "0xToken"
        assert details.price == {"EUR": Dezimal("2700")}

    @pytest.mark.asyncio
    async def test_get_asset_details_unknown_returns_none(self):
        client = _client(_dataset())

        assert await client.get_asset_details("999", ["EUR"]) is None

    @pytest.mark.asyncio
    async def test_empty_when_dataset_unavailable(self):
        client = _client(None)

        assert await client.search("btc") == []
        assert await client.get_prices(["BTC"], ["EUR"]) == {}
        assert await client.asset_lookup(symbol="btc") == []
        assert await client.get_asset_platforms() == {}
        assert await client.get_asset_details("1", ["EUR"]) is None
