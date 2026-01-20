import logging
from typing import Optional

from aiocache import cached
from aiocache.serializers import PickleSerializer

from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from domain.crypto import (
    AvailableCryptoAsset,
    CryptoAsset,
    CryptoAssetDetails,
    CryptoPlatform,
)
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.rates.crypto.coingecko_client import CoinGeckoClient
from infrastructure.client.rates.crypto.cryptocompare_client import CryptoCompareClient
from infrastructure.client.rates.crypto.p2s_client import P2SClient


from infrastructure.client.rates.crypto.coingecko_cache_strategy import (
    CoinGeckoCacheStrategy,
)


class CryptoAssetInfoClient(CryptoAssetInfoProvider):
    PRICE_CACHE_TTL = 20 * 60

    def __init__(self, coingecko_strategy: CoinGeckoCacheStrategy):
        self._p2s_client = P2SClient()
        self._coingecko_client = CoinGeckoClient(cache_strategy=coingecko_strategy)
        self._cc_client = CryptoCompareClient()

        self._log = logging.getLogger(__name__)

    async def initialize(self):
        await self._coingecko_client.initialize()

    @cached(
        ttl=PRICE_CACHE_TTL,
        key_builder=lambda f,
        self,
        symbol,
        fiat_iso,
        **kwargs: f"crypto_price:{symbol.upper()}_{fiat_iso.upper()}",
        serializer=PickleSerializer(),
    )
    async def get_price(self, symbol: str, fiat_iso: str, **kwargs) -> Dezimal:
        timeout = kwargs.get("timeout")
        if self._p2s_client.supports_symbol(symbol):
            return await self._p2s_client.get_price(symbol, fiat_iso, timeout)

        return (
            (await self.get_multiple_prices_by_symbol([symbol], [fiat_iso]))
            .get(symbol, {})
            .get(fiat_iso, Dezimal(1))
        )

    @cached(
        ttl=PRICE_CACHE_TTL,
        key_builder=lambda f,
        self,
        symbols,
        fiat_isos,
        **kwargs: f"crypto_multi_price:{','.join(sorted(symbols)).upper()}_{','.join(sorted(fiat_isos)).upper()}",
        serializer=PickleSerializer(),
    )
    async def get_multiple_prices_by_symbol(
        self, symbols: list[str], fiat_isos: list[str], **kwargs
    ) -> dict[str, dict[str, Dezimal]]:
        timeout = kwargs.get("timeout")
        result = {}

        coingecko_prices = await self._cc_client.get_prices(symbols, fiat_isos, timeout)
        for sym, prices in coingecko_prices.items():
            result[sym] = prices

        missing_symbols = [s for s in symbols if s not in result]
        if missing_symbols:
            missing_prices = await self._coingecko_client.get_prices(
                missing_symbols, fiat_isos, timeout
            )
            for sym, prices in missing_prices.items():
                result[sym] = prices

        # { crypto_symbol: { fiat_iso: Dezimal(price) } }
        return result

    @cached(
        ttl=PRICE_CACHE_TTL,
        key_builder=lambda f,
        self,
        addresses,
        fiat_isos,
        **kwargs: f"crypto_addr_price:{','.join(sorted(a.lower() for a in addresses))}_{','.join(sorted(f.upper() for f in fiat_isos))}",
        serializer=PickleSerializer(),
    )
    async def get_prices_by_addresses(
        self, addresses: list[str], fiat_isos: list[str], **kwargs
    ) -> dict[str, dict[str, Dezimal]]:
        timeout = kwargs.get("timeout")
        return await self._coingecko_client.get_prices_by_addresses(
            addresses, fiat_isos, timeout or self._coingecko_client.TIMEOUT
        )

    @cached(
        ttl=86400,
        key_builder=lambda f, self, symbol: f"crypto_by_symbol:{symbol.upper()}",
        serializer=PickleSerializer(),
    )
    async def get_by_symbol(self, symbol: str) -> list[CryptoAsset]:
        try:
            assets = await self._cc_client.search(symbol)
            if assets:
                return assets
        except Exception as e:
            self._log.error(f"CryptoCompare search failed for {symbol}: {e}")

        self._log.info(f"Backing off to CoinGecko search for symbol {symbol}")
        return await self._coingecko_client.search(symbol)

    async def get_multiple_overview_by_addresses(
        self, addresses: list[str]
    ) -> dict[str, CryptoAsset]:
        if not addresses:
            return {}
        overview = await self._coingecko_client.get_coin_overview_by_addresses(
            addresses
        )
        result: dict[str, CryptoAsset] = {}
        for raw, coin in overview.items():
            asset = CryptoAsset(
                name=coin.get("name"),
                symbol=coin.get("symbol"),
                icon_urls=[],
                external_ids={"COINGECKO": coin.get("id")},
            )
            result[raw] = asset
        return result

    async def asset_lookup(
        self, symbol: str | None = None, name: str | None = None
    ) -> list[AvailableCryptoAsset]:
        return await self._coingecko_client.asset_lookup(symbol=symbol, name=name)

    async def get_asset_platforms(self) -> dict[str, CryptoPlatform]:
        return await self._coingecko_client.get_asset_platforms()

    @cached(
        ttl=3600,
        key_builder=lambda f,
        self,
        provider_id,
        currencies,
        provider=ExternalIntegrationId.COINGECKO: f"crypto_asset_details:{provider_id}_{'_'.join(sorted(currencies))}",
        serializer=PickleSerializer(),
    )
    async def get_asset_details(
        self,
        provider_id: str,
        currencies: list[str],
        provider: ExternalIntegrationId = ExternalIntegrationId.COINGECKO,
    ) -> CryptoAssetDetails:
        if provider == ExternalIntegrationId.COINGECKO:
            return await self._coingecko_client.get_asset_details(
                provider_id=provider_id, currencies=currencies
            )
        raise NotImplementedError(
            f"Asset details not implemented for provider {provider}"
        )

    async def get_native_entity_by_platform(
        self, provider_id: str, provider: ExternalIntegrationId
    ) -> Optional[Entity]:
        if provider == ExternalIntegrationId.COINGECKO:
            return self._coingecko_client.get_native_entity_by_platform(
                provider_id, provider
            )
        raise NotImplementedError(
            f"Native entity lookup not implemented for provider {provider}"
        )
