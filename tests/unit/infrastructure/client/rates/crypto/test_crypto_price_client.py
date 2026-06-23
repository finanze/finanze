from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.crypto import CryptoAsset
from domain.dezimal import Dezimal
from infrastructure.client.rates.crypto.crypto_price_client import (
    CryptoAssetInfoClient,
)


def _build_client() -> CryptoAssetInfoClient:
    client = CryptoAssetInfoClient(coingecko_strategy=MagicMock())
    client._coingecko_client = AsyncMock()
    client._cc_client = AsyncMock()
    client._p2s_client = MagicMock()
    client._p2s_client.supports_symbol.return_value = False
    return client


class TestGetMultiplePricesBySymbol:
    @pytest.mark.asyncio
    async def test_coingecko_is_primary(self):
        client = _build_client()
        client._coingecko_client.get_prices.return_value = {
            "AAA": {"EUR": Dezimal("10")}
        }

        result = await client.get_multiple_prices_by_symbol(["AAA"], ["EUR"])

        assert result == {"AAA": {"EUR": Dezimal("10")}}
        client._coingecko_client.get_prices.assert_awaited_once()
        client._cc_client.get_prices.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cryptocompare_fills_missing_symbols(self):
        client = _build_client()
        client._coingecko_client.get_prices.return_value = {
            "BBB": {"EUR": Dezimal("20")}
        }
        client._cc_client.get_prices.return_value = {"CCC": {"EUR": Dezimal("30")}}

        result = await client.get_multiple_prices_by_symbol(["BBB", "CCC"], ["EUR"])

        assert result == {
            "BBB": {"EUR": Dezimal("20")},
            "CCC": {"EUR": Dezimal("30")},
        }
        client._cc_client.get_prices.assert_awaited_once_with(["CCC"], ["EUR"], None)

    @pytest.mark.asyncio
    async def test_coingecko_failure_falls_back_to_cryptocompare(self):
        client = _build_client()
        client._coingecko_client.get_prices.side_effect = RuntimeError("boom")
        client._cc_client.get_prices.return_value = {"DDD": {"EUR": Dezimal("40")}}

        result = await client.get_multiple_prices_by_symbol(["DDD"], ["EUR"])

        assert result == {"DDD": {"EUR": Dezimal("40")}}
        client._cc_client.get_prices.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cryptocompare_failure_is_swallowed(self):
        client = _build_client()
        client._coingecko_client.get_prices.return_value = {
            "EEE": {"EUR": Dezimal("50")}
        }
        client._cc_client.get_prices.side_effect = RuntimeError("no key")

        result = await client.get_multiple_prices_by_symbol(["EEE", "FFF"], ["EUR"])

        assert result == {"EEE": {"EUR": Dezimal("50")}}


class TestGetBySymbol:
    @pytest.mark.asyncio
    async def test_coingecko_is_primary(self):
        client = _build_client()
        asset = CryptoAsset(name="Gecko", symbol="GGG", icon_urls=None, external_ids={})
        client._coingecko_client.search.return_value = [asset]

        result = await client.get_by_symbol("GGG")

        assert result == [asset]
        client._coingecko_client.search.assert_awaited_once_with("GGG")
        client._cc_client.search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_cryptocompare_when_empty(self):
        client = _build_client()
        cc_asset = CryptoAsset(
            name="Compare", symbol="HHH", icon_urls=None, external_ids={}
        )
        client._coingecko_client.search.return_value = []
        client._cc_client.search.return_value = [cc_asset]

        result = await client.get_by_symbol("HHH")

        assert result == [cc_asset]
        client._cc_client.search.assert_awaited_once_with("HHH")

    @pytest.mark.asyncio
    async def test_returns_empty_when_both_fail(self):
        client = _build_client()
        client._coingecko_client.search.side_effect = RuntimeError("boom")
        client._cc_client.search.side_effect = RuntimeError("no key")

        result = await client.get_by_symbol("III")

        assert result == []
