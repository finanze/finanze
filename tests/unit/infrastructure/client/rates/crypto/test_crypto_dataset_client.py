from unittest.mock import AsyncMock, MagicMock

import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from domain.dezimal import Dezimal
from infrastructure.client.rates.crypto.crypto_dataset_client import (
    CryptoDatasetClient,
)


def _raw_with_age(raw: dict, age: timedelta) -> dict:
    clone = copy.deepcopy(raw)
    clone["updated_at"] = (
        (datetime.now(timezone.utc) - age).isoformat().replace("+00:00", "Z")
    )
    return clone


def _stub_session(client: CryptoDatasetClient, raw, ok: bool = True):
    response = MagicMock()
    response.ok = ok
    response.status = 200 if ok else 500
    response.json = AsyncMock(return_value=raw)
    response.text = AsyncMock(return_value="boom")
    client._session = MagicMock()
    client._session.get = AsyncMock(return_value=response)
    return client._session


CG_RAW = {
    "updated_at": "2026-06-22T16:59:18Z",
    "base_fiats": ["USD", "EUR"],
    "coin_icon_base": "https://icons/coins/",
    "platform_icon_base": "https://icons/platforms/",
    "coins": [
        {
            "i": "bitcoin",
            "s": "btc",
            "n": "Bitcoin",
            "ic": "1.png",
            "p": {"USD": "64661.21", "EUR": "56575.39"},
        },
        {
            "i": "some-token",
            "s": "tok",
            "n": "Some Token",
            "pt": {"ethereum": "0xAbC123"},
            "p": {"EUR": "1.5"},
        },
    ],
    "platforms": {
        "ethereum": {"n": "Ethereum", "ic": "279.png"},
    },
}

CMC_RAW = {
    "updated_at": "2026-06-22T16:59:18Z",
    "base_fiats": ["USD", "EUR"],
    "coin_icon_base": "https://s2.cmc/coins/",
    "coins": [
        {
            "i": 1,
            "s": "BTC",
            "n": "Bitcoin",
            "ic": "1.png",
            "p": {"USD": "64661.21", "EUR": "56575.39"},
        },
        {
            "i": 1027,
            "s": "ETH",
            "n": "Ethereum",
            "ic": "1027.png",
            "pt": {"ethereum": "0xToken"},
            "p": {"USD": "3000", "EUR": "2700"},
        },
    ],
    "platforms": {
        "ethereum": {"n": "Ethereum"},
    },
}


class TestBuild:
    def test_builds_coingecko_shape(self):
        client = CryptoDatasetClient()
        dataset = client._build(CG_RAW)

        assert dataset is not None
        btc = dataset.coin_by_id("bitcoin")
        assert btc.symbol == "btc"
        assert btc.icon_url == "https://icons/coins/1.png"
        assert btc.prices == {"USD": Dezimal("64661.21"), "EUR": Dezimal("56575.39")}

        token = dataset.coin_by_id("some-token")
        assert token.platforms == {"ethereum": "0xAbC123"}

        platform = dataset.platforms["ethereum"]
        assert platform.name == "Ethereum"
        assert platform.icon_url == "https://icons/platforms/279.png"

    def test_builds_coinmarketcap_shape(self):
        client = CryptoDatasetClient()
        dataset = client._build(CMC_RAW)

        assert dataset is not None
        # Integer ids are normalized to strings.
        btc = dataset.coin_by_id("1")
        assert btc.symbol == "BTC"
        assert btc.icon_url == "https://s2.cmc/coins/1.png"
        # CMC platforms carry no icon.
        assert dataset.platforms["ethereum"].icon_url is None

    def test_returns_none_for_invalid(self):
        client = CryptoDatasetClient()
        assert client._build({}) is None
        assert client._build({"coins": []}) is None
        assert client._build("nonsense") is None


class TestLookups:
    def test_prices_by_symbols_and_addresses(self):
        client = CryptoDatasetClient()
        dataset = client._build(CMC_RAW)

        by_symbol = dataset.prices_by_symbols(["ETH"], ["EUR", "USD"])
        assert by_symbol == {"ETH": {"EUR": Dezimal("2700"), "USD": Dezimal("3000")}}

        by_address = dataset.prices_by_addresses(["0xTOKEN"], ["EUR"])
        assert by_address == {"0xtoken": {"EUR": Dezimal("2700")}}

    def test_to_coingecko_shapes(self):
        client = CryptoDatasetClient()
        dataset = client._build(CG_RAW)

        coin_list = dataset.to_coingecko_coin_list()
        assert {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "platforms": {},
        } in coin_list

        platforms = dataset.to_coingecko_platforms()
        assert {
            "id": "ethereum",
            "name": "Ethereum",
            "image": {"large": "https://icons/platforms/279.png"},
        } in platforms


class TestLoad:
    @pytest.mark.asyncio
    async def test_load_parses_and_caches(self):
        client = CryptoDatasetClient()
        response = MagicMock()
        response.ok = True
        response.json = AsyncMock(return_value=CG_RAW)
        client._session = MagicMock()
        client._session.get = AsyncMock(return_value=response)

        dataset = await client.load_coingecko()
        assert dataset is not None
        assert dataset.coin_by_id("bitcoin") is not None

        # Second call is served from cache (no extra fetch).
        await client.load_coingecko()
        client._session.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_load_returns_none_on_http_error(self):
        client = CryptoDatasetClient()
        response = MagicMock()
        response.ok = False
        response.status = 500
        response.text = AsyncMock(return_value="boom")
        client._session = MagicMock()
        client._session.get = AsyncMock(return_value=response)

        assert await client.load_coinmarketcap() is None


class TestStorePersistence:
    @pytest.mark.asyncio
    async def test_persists_to_store_on_cloud_success(self):
        store = AsyncMock()
        store.load.return_value = None
        client = CryptoDatasetClient(store=store)
        response = MagicMock()
        response.ok = True
        response.json = AsyncMock(return_value=CG_RAW)
        client._session = MagicMock()
        client._session.get = AsyncMock(return_value=response)

        dataset = await client.load_coingecko()
        assert dataset is not None
        store.save.assert_awaited_once()
        key, raw_text = store.save.await_args.args
        assert key == "cg"
        assert json.loads(raw_text) == CG_RAW

    @pytest.mark.asyncio
    async def test_falls_back_to_store_when_cloud_fails(self):
        store = AsyncMock()
        store.load.return_value = json.dumps(CMC_RAW)
        client = CryptoDatasetClient(store=store)
        response = MagicMock()
        response.ok = False
        response.status = 500
        response.text = AsyncMock(return_value="boom")
        client._session = MagicMock()
        client._session.get = AsyncMock(return_value=response)

        dataset = await client.load_coinmarketcap()
        assert dataset is not None
        assert dataset.coin_by_id("1") is not None
        store.load.assert_awaited_once_with("cmc")
        store.save.assert_not_awaited()


class TestFreshness:
    @pytest.mark.asyncio
    async def test_fresh_file_served_without_network(self):
        store = AsyncMock()
        store.load.return_value = json.dumps(_raw_with_age(CG_RAW, timedelta(days=1)))
        client = CryptoDatasetClient(store=store)
        session = _stub_session(client, CG_RAW)

        dataset = await client.load_coingecko()
        assert dataset is not None
        session.get.assert_not_awaited()
        store.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stale_file_triggers_refresh_and_resave(self):
        store = AsyncMock()
        store.load.return_value = json.dumps(_raw_with_age(CG_RAW, timedelta(days=10)))
        client = CryptoDatasetClient(store=store)
        fresh = _raw_with_age(CG_RAW, timedelta(minutes=5))
        session = _stub_session(client, fresh)

        dataset = await client.load_coingecko()
        assert dataset is not None
        session.get.assert_awaited_once()
        store.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_offline_serves_stale_file(self):
        store = AsyncMock()
        store.load.return_value = json.dumps(_raw_with_age(CG_RAW, timedelta(days=10)))
        client = CryptoDatasetClient(store=store)
        session = _stub_session(client, None, ok=False)

        dataset = await client.load_coingecko()
        assert dataset is not None
        assert dataset.coin_by_id("bitcoin") is not None
        session.get.assert_awaited_once()
        store.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cooldown_prevents_refetch_storm(self):
        store = AsyncMock()
        store.load.return_value = json.dumps(_raw_with_age(CG_RAW, timedelta(days=10)))
        client = CryptoDatasetClient(store=store)
        session = _stub_session(client, None, ok=False)

        first = await client.load_coingecko()
        second = await client.load_coingecko()
        assert first is not None and second is not None
        # Both calls reuse the same in-cooldown stale dataset; only one fetch.
        assert session.get.await_count == 1

    @pytest.mark.asyncio
    async def test_price_threshold_stricter_than_list(self):
        # A copy that is fresh for the 5-day list window but stale for 6h prices.
        store = AsyncMock()
        store.load.return_value = json.dumps(_raw_with_age(CG_RAW, timedelta(hours=12)))
        client = CryptoDatasetClient(store=store)
        fresh = _raw_with_age(CG_RAW, timedelta(minutes=1))
        session = _stub_session(client, fresh)

        # List load is satisfied by the 12h-old file, no network.
        await client.load_coingecko()
        session.get.assert_not_awaited()

        # Price load needs <6h freshness, so it refreshes from the endpoint.
        await client.load_coingecko(max_age=CryptoDatasetClient.PRICE_MAX_AGE)
        session.get.assert_awaited_once()
        store.save.assert_awaited_once()
