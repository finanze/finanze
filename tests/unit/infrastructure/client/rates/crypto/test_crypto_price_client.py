from unittest.mock import AsyncMock, MagicMock

import pytest
from datetime import datetime, timezone

from domain.crypto import AvailableCryptoAsset, CryptoAsset, CryptoPlatform
from domain.dezimal import Dezimal
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.rates.crypto.crypto_dataset_client import (
    CryptoDataset,
    CryptoDatasetCoin,
)
from infrastructure.client.rates.crypto.crypto_price_client import (
    CryptoAssetInfoClient,
)


def _dataset_with_coin(
    coin_id: str,
    symbol: str,
    prices: dict,
    platforms: dict | None = None,
) -> CryptoDataset:
    coin = CryptoDatasetCoin(
        id=coin_id,
        symbol=symbol,
        name=coin_id.title(),
        icon_url=None,
        platforms=platforms or {},
        prices=prices,
    )
    return CryptoDataset(
        updated_at=datetime.now(timezone.utc), coins=[coin], platforms={}
    )


def _build_client() -> CryptoAssetInfoClient:
    client = CryptoAssetInfoClient()
    client._coingecko_client = AsyncMock()
    client._cmc_client = AsyncMock()
    client._cc_client = AsyncMock()
    client._dataset_client = AsyncMock()
    client._dataset_client.load_coingecko.return_value = None
    client._dataset_client.load_coinmarketcap.return_value = None
    client._cmc_client.get_prices.return_value = {}
    client._cmc_client.get_prices_by_addresses.return_value = {}
    client._cmc_client.search.return_value = []
    client._cmc_client.asset_lookup.return_value = []
    client._cmc_client.get_asset_platforms.return_value = {}
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
        client._dataset_client.load_coingecko.assert_not_awaited()
        client._cmc_client.get_prices.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_partial_cg_result_no_further_fallback(self):
        client = _build_client()
        client._coingecko_client.get_prices.return_value = {
            "BBB": {"EUR": Dezimal("20")}
        }

        result = await client.get_multiple_prices_by_symbol(["BBB", "CCC"], ["EUR"])

        assert result == {"BBB": {"EUR": Dezimal("20")}}
        client._dataset_client.load_coingecko.assert_not_awaited()
        client._cmc_client.get_prices.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_coingecko_failure_uses_cg_snapshot(self):
        client = _build_client()
        client._coingecko_client.get_prices.side_effect = RuntimeError("boom")
        client._dataset_client.load_coingecko.return_value = _dataset_with_coin(
            "ddd4", "DDD4", {"EUR": Dezimal("40")}
        )

        result = await client.get_multiple_prices_by_symbol(["DDD4"], ["EUR"])

        assert result == {"DDD4": {"EUR": Dezimal("40")}}
        client._dataset_client.load_coingecko.assert_awaited_once()
        client._cmc_client.get_prices.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_coingecko_empty_uses_cg_snapshot(self):
        client = _build_client()
        client._coingecko_client.get_prices.return_value = {}
        client._dataset_client.load_coingecko.return_value = _dataset_with_coin(
            "snap", "SNP", {"EUR": Dezimal("7")}
        )

        result = await client.get_multiple_prices_by_symbol(["SNP"], ["EUR"])

        assert result == {"SNP": {"EUR": Dezimal("7")}}
        client._dataset_client.load_coingecko.assert_awaited_once()
        client._cmc_client.get_prices.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cmc_fills_when_cg_snapshot_unavailable(self):
        client = _build_client()
        client._coingecko_client.get_prices.return_value = {}
        client._dataset_client.load_coingecko.return_value = None
        client._cmc_client.get_prices.return_value = {"MNO": {"EUR": Dezimal("2")}}

        result = await client.get_multiple_prices_by_symbol(["MNO"], ["EUR"])

        assert result == {"MNO": {"EUR": Dezimal("2")}}
        client._dataset_client.load_coingecko.assert_awaited_once()
        client._cmc_client.get_prices.assert_awaited_once_with(["MNO"], ["EUR"])

    @pytest.mark.asyncio
    async def test_partial_cg_result_no_snapshot_no_cmc(self):
        client = _build_client()
        client._coingecko_client.get_prices.return_value = {
            "PPP": {"EUR": Dezimal("1")}
        }

        result = await client.get_multiple_prices_by_symbol(["PPP", "QQQ"], ["EUR"])

        assert result == {"PPP": {"EUR": Dezimal("1")}}
        client._dataset_client.load_coingecko.assert_not_awaited()
        client._cmc_client.get_prices.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_coingecko_raises_snapshot_consulted(self):
        client = _build_client()
        client._coingecko_client.get_prices.side_effect = RuntimeError("timeout")
        client._dataset_client.load_coingecko.return_value = _dataset_with_coin(
            "snap2", "SNP2", {"EUR": Dezimal("7")}
        )

        result = await client.get_multiple_prices_by_symbol(["SNP2"], ["EUR"])

        assert result == {"SNP2": {"EUR": Dezimal("7")}}
        client._dataset_client.load_coingecko.assert_awaited_once()
        client._cmc_client.get_prices.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cg_empty_snapshot_fails_result_empty(self):
        client = _build_client()
        client._coingecko_client.get_prices.return_value = {}
        client._dataset_client.load_coingecko.return_value = None
        client._cmc_client.get_prices.return_value = {}

        result = await client.get_multiple_prices_by_symbol(["ZZZ"], ["EUR"])

        assert result == {}
        client._cmc_client.get_prices.assert_awaited_once_with(["ZZZ"], ["EUR"])


class TestGetPricesByAddresses:
    @pytest.mark.asyncio
    async def test_coingecko_is_primary(self):
        client = _build_client()
        client._coingecko_client.get_prices_by_addresses.return_value = {
            "0xabc": {"EUR": Dezimal("3")}
        }

        result = await client.get_prices_by_addresses(["0xABC"], ["EUR"])

        assert result == {"0xabc": {"EUR": Dezimal("3")}}
        client._cmc_client.get_prices_by_addresses.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cmc_fallback_for_unresolved_addresses(self):
        client = _build_client()
        client._coingecko_client.get_prices_by_addresses.return_value = {}
        client._cmc_client.get_prices_by_addresses.return_value = {
            "0xdef": {"EUR": Dezimal("4")}
        }

        result = await client.get_prices_by_addresses(["0xDEF"], ["EUR"])

        assert result == {"0xdef": {"EUR": Dezimal("4")}}
        client._cmc_client.get_prices_by_addresses.assert_awaited_once_with(
            ["0xDEF"], ["EUR"]
        )

    @pytest.mark.asyncio
    async def test_coingecko_snapshot_before_cmc(self):
        client = _build_client()
        client._coingecko_client.get_prices_by_addresses.return_value = {}
        client._dataset_client.load_coingecko.return_value = _dataset_with_coin(
            "tok", "TOK", {"EUR": Dezimal("5")}, platforms={"ethereum": "0xfff"}
        )

        result = await client.get_prices_by_addresses(["0xFFF"], ["EUR"])

        assert result == {"0xfff": {"EUR": Dezimal("5")}}
        client._cmc_client.get_prices_by_addresses.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_partial_cg_result_skips_snapshot_uses_cmc(self):
        client = _build_client()
        client._coingecko_client.get_prices_by_addresses.return_value = {
            "0xaaa": {"EUR": Dezimal("3")}
        }

        result = await client.get_prices_by_addresses(["0xAAA", "0xBBB"], ["EUR"])

        assert result == {"0xaaa": {"EUR": Dezimal("3")}}
        client._dataset_client.load_coingecko.assert_not_awaited()
        client._cmc_client.get_prices_by_addresses.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_coingecko_raises_snapshot_consulted(self):
        client = _build_client()
        client._coingecko_client.get_prices_by_addresses.side_effect = RuntimeError(
            "down"
        )
        client._dataset_client.load_coingecko.return_value = _dataset_with_coin(
            "tok2", "TOK2", {"EUR": Dezimal("5")}, platforms={"ethereum": "0xeee"}
        )

        result = await client.get_prices_by_addresses(["0xEEE"], ["EUR"])

        assert result == {"0xeee": {"EUR": Dezimal("5")}}
        client._dataset_client.load_coingecko.assert_awaited_once()
        client._cmc_client.get_prices_by_addresses.assert_not_awaited()


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
    async def test_cmc_used_before_cryptocompare(self):
        client = _build_client()
        cmc_asset = CryptoAsset(
            name="Market", symbol="MMM", icon_urls=None, external_ids={}
        )
        client._coingecko_client.search.return_value = []
        client._cmc_client.search.return_value = [cmc_asset]

        result = await client.get_by_symbol("MMM")

        assert result == [cmc_asset]
        client._cmc_client.search.assert_awaited_once_with("MMM")
        client._cc_client.search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_empty_when_both_fail(self):
        client = _build_client()
        client._coingecko_client.search.side_effect = RuntimeError("boom")
        client._cc_client.search.side_effect = RuntimeError("no key")

        result = await client.get_by_symbol("III")

        assert result == []


class TestAssetLookup:
    @pytest.mark.asyncio
    async def test_coingecko_results_returned_without_cmc(self):
        client = _build_client()
        cg_asset = AvailableCryptoAsset(
            name="Ether",
            symbol="ETH",
            platforms=[],
            provider=ExternalIntegrationId.COINGECKO,
            provider_id="ethereum",
        )
        client._coingecko_client.asset_lookup.return_value = [cg_asset]

        result = await client.asset_lookup(symbol="eth")

        assert result == [cg_asset]
        client._cmc_client.asset_lookup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_cmc_when_coingecko_empty(self):
        client = _build_client()
        cmc_asset = AvailableCryptoAsset(
            name="Ether",
            symbol="ETH",
            platforms=[],
            provider=ExternalIntegrationId.COINMARKETCAP,
            provider_id="1027",
        )
        client._coingecko_client.asset_lookup.return_value = []
        client._cmc_client.asset_lookup.return_value = [cmc_asset]

        result = await client.asset_lookup(symbol="eth")

        assert result == [cmc_asset]
        client._cmc_client.asset_lookup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_cmc_when_coingecko_fails(self):
        client = _build_client()
        cmc_asset = AvailableCryptoAsset(
            name="Ether",
            symbol="ETH",
            platforms=[],
            provider=ExternalIntegrationId.COINMARKETCAP,
            provider_id="1027",
        )
        client._coingecko_client.asset_lookup.side_effect = RuntimeError("boom")
        client._cmc_client.asset_lookup.return_value = [cmc_asset]

        result = await client.asset_lookup(symbol="eth")

        assert result == [cmc_asset]


class TestGetAssetPlatforms:
    @pytest.mark.asyncio
    async def test_coingecko_platforms_returned_without_cmc(self):
        client = _build_client()
        platforms = {
            "ethereum": CryptoPlatform(
                provider_id="ethereum", name="Ethereum", icon_url=None
            )
        }
        client._coingecko_client.get_asset_platforms.return_value = platforms

        result = await client.get_asset_platforms()

        assert result == platforms
        client._cmc_client.get_asset_platforms.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_cmc_when_coingecko_empty(self):
        client = _build_client()
        cmc_platforms = {
            "ethereum": CryptoPlatform(
                provider_id="ethereum", name="Ethereum", icon_url=None
            )
        }
        client._coingecko_client.get_asset_platforms.return_value = {}
        client._cmc_client.get_asset_platforms.return_value = cmc_platforms

        result = await client.get_asset_platforms()

        assert result == cmc_platforms
        client._cmc_client.get_asset_platforms.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_cmc_when_coingecko_fails(self):
        client = _build_client()
        cmc_platforms = {
            "ethereum": CryptoPlatform(
                provider_id="ethereum", name="Ethereum", icon_url=None
            )
        }
        client._coingecko_client.get_asset_platforms.side_effect = RuntimeError("boom")
        client._cmc_client.get_asset_platforms.return_value = cmc_platforms

        result = await client.get_asset_platforms()

        assert result == cmc_platforms


class TestGetAssetDetails:
    @pytest.mark.asyncio
    async def test_coingecko_is_default_provider(self):
        client = _build_client()
        details = object()
        client._coingecko_client.get_asset_details.return_value = details

        result = await client.get_asset_details("bitcoin", ["EUR"])

        assert result is details
        client._cmc_client.get_asset_details.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_coinmarketcap_routes_to_cmc_dataset(self):
        client = _build_client()
        details = object()
        client._cmc_client.get_asset_details.return_value = details

        result = await client.get_asset_details(
            "1027", ["EUR"], provider=ExternalIntegrationId.COINMARKETCAP
        )

        assert result is details
        client._cmc_client.get_asset_details.assert_awaited_once_with("1027", ["EUR"])
        client._coingecko_client.get_asset_details.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_coinmarketcap_raises_when_unavailable(self):
        client = _build_client()
        client._cmc_client.get_asset_details.return_value = None

        with pytest.raises(ValueError):
            await client.get_asset_details(
                "404", ["EUR"], provider=ExternalIntegrationId.COINMARKETCAP
            )
