import logging
from datetime import timedelta
from typing import Optional

from aiocache import cached
from aiocache.serializers import PickleSerializer

from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from domain.crypto import (
    AvailableCryptoAsset,
    CryptoAsset,
    CryptoAssetDetails,
    CryptoAssetPlatform,
    CryptoCurrencyType,
    CryptoPlatform,
)
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.rates.crypto.coingecko_client import CoinGeckoClient
from infrastructure.client.rates.crypto.coinmarketcap_dataset_client import (
    CoinMarketCapDatasetClient,
)
from infrastructure.client.rates.crypto.cryptocompare_client import CryptoCompareClient
from infrastructure.client.rates.crypto.p2s_client import P2SClient


from infrastructure.client.rates.crypto.crypto_dataset_client import (
    CryptoDataset,
    CryptoDatasetClient,
)
from infrastructure.client.rates.crypto.crypto_dataset_store import (
    CryptoDatasetStore,
)


class CryptoAssetInfoClient(CryptoAssetInfoProvider):
    PRICE_CACHE_TTL = 20 * 60

    def __init__(self, dataset_store: Optional[CryptoDatasetStore] = None):
        self._p2s_client = P2SClient()
        self._dataset_client = CryptoDatasetClient(store=dataset_store)
        self._coingecko_client = CoinGeckoClient(dataset_client=self._dataset_client)
        self._cmc_client = CoinMarketCapDatasetClient(self._dataset_client)
        self._cc_client = CryptoCompareClient()

        self._log = logging.getLogger(__name__)

    async def initialize(self):
        await self._coingecko_client.initialize()

    @cached(
        ttl=PRICE_CACHE_TTL,
        key_builder=lambda f, self, symbol, fiat_iso, **kwargs: (
            f"crypto_price:{symbol.upper()}_{fiat_iso.upper()}"
        ),
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
        key_builder=lambda f, self, symbols, fiat_isos, **kwargs: (
            f"crypto_multi_price:{','.join(sorted(symbols)).upper()}_{','.join(sorted(fiat_isos)).upper()}"
        ),
        serializer=PickleSerializer(),
    )
    async def get_multiple_prices_by_symbol(
        self, symbols: list[str], fiat_isos: list[str], **kwargs
    ) -> dict[str, dict[str, Dezimal]]:
        timeout = kwargs.get("timeout")
        result = {}

        try:
            cg_prices = await self._coingecko_client.get_prices(
                symbols, fiat_isos, timeout
            )
            for sym, prices in cg_prices.items():
                result[sym] = prices
        except Exception as e:
            self._log.warning(f"CoinGecko prices fetch failed: {e}")

        missing_symbols = [s for s in symbols if s not in result]
        if missing_symbols:
            snapshot = await self._coingecko_snapshot_prices(missing_symbols, fiat_isos)
            for sym, prices in snapshot.items():
                result.setdefault(sym, prices)

        missing_symbols = [s for s in symbols if s not in result]
        if missing_symbols:
            try:
                cmc_prices = await self._cmc_client.get_prices(
                    missing_symbols, fiat_isos
                )
                for sym, prices in cmc_prices.items():
                    result.setdefault(sym, prices)
            except Exception as e:
                self._log.warning(f"CoinMarketCap prices fetch failed: {e}")

        missing_symbols = [s for s in symbols if s not in result]
        if missing_symbols:
            try:
                missing_prices = await self._cc_client.get_prices(
                    missing_symbols, fiat_isos, timeout
                )
                for sym, prices in missing_prices.items():
                    result.setdefault(sym, prices)
            except Exception as e:
                self._log.warning(f"CryptoCompare prices fetch failed: {e}")

        # { crypto_symbol: { fiat_iso: Dezimal(price) } }
        return result

    @cached(
        ttl=PRICE_CACHE_TTL,
        key_builder=lambda f, self, addresses, fiat_isos, **kwargs: (
            f"crypto_addr_price:{','.join(sorted(a.lower() for a in addresses))}_{','.join(sorted(f.upper() for f in fiat_isos))}"
        ),
        serializer=PickleSerializer(),
    )
    async def get_prices_by_addresses(
        self, addresses: list[str], fiat_isos: list[str], **kwargs
    ) -> dict[str, dict[str, Dezimal]]:
        timeout = kwargs.get("timeout")
        result: dict[str, dict[str, Dezimal]] = {}
        try:
            result = await self._coingecko_client.get_prices_by_addresses(
                addresses, fiat_isos, timeout or self._coingecko_client.TIMEOUT
            )
        except Exception as e:
            self._log.warning(f"CoinGecko address prices fetch failed: {e}")
            result = {}

        missing = self._missing_addresses(addresses, result)
        if missing:
            cg_dataset = await self._safe_cg_dataset(CryptoDatasetClient.PRICE_MAX_AGE)
            if cg_dataset is not None:
                for addr, prices in cg_dataset.prices_by_addresses(
                    missing, fiat_isos
                ).items():
                    result.setdefault(addr, prices)

        missing = self._missing_addresses(addresses, result)
        if missing:
            try:
                cmc_prices = await self._cmc_client.get_prices_by_addresses(
                    missing, fiat_isos
                )
                for addr, prices in cmc_prices.items():
                    result.setdefault(addr, prices)
            except Exception as e:
                self._log.warning(f"CoinMarketCap address prices fetch failed: {e}")

        return result

    @cached(
        ttl=86400,
        key_builder=lambda f, self, symbol: f"crypto_by_symbol:{symbol.upper()}",
        serializer=PickleSerializer(),
    )
    async def get_by_symbol(self, symbol: str) -> list[CryptoAsset]:
        try:
            assets = await self._coingecko_client.search(symbol)
            if assets:
                return assets
        except Exception as e:
            self._log.error(f"CoinGecko search failed for {symbol}: {e}")

        try:
            cmc_assets = await self._cmc_client.search(symbol)
            if cmc_assets:
                return cmc_assets
        except Exception as e:
            self._log.error(f"CoinMarketCap search failed for {symbol}: {e}")

        self._log.info(f"Backing off to CryptoCompare search for symbol {symbol}")
        try:
            return await self._cc_client.search(symbol)
        except Exception as e:
            self._log.error(f"CryptoCompare search failed for {symbol}: {e}")
            return []

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
        try:
            results = await self._coingecko_client.asset_lookup(
                symbol=symbol, name=name
            )
            if results:
                return results
        except Exception as e:
            self._log.warning(f"CoinGecko asset lookup failed: {e}")

        try:
            return await self._cmc_client.asset_lookup(symbol=symbol, name=name)
        except Exception as e:
            self._log.warning(f"CoinMarketCap asset lookup failed: {e}")
            return []

    async def get_asset_platforms(self) -> dict[str, CryptoPlatform]:
        try:
            platforms = await self._coingecko_client.get_asset_platforms()
            if platforms:
                return platforms
        except Exception as e:
            self._log.warning(f"CoinGecko asset platforms failed: {e}")

        try:
            return await self._cmc_client.get_asset_platforms()
        except Exception as e:
            self._log.warning(f"CoinMarketCap asset platforms failed: {e}")
            return {}

    @cached(
        ttl=3600,
        key_builder=lambda f, self, provider_id, currencies, provider=ExternalIntegrationId.COINGECKO: (
            f"crypto_asset_details:{provider.value}:{provider_id}_{'_'.join(sorted(currencies))}"
        ),
        serializer=PickleSerializer(),
    )
    async def get_asset_details(
        self,
        provider_id: str,
        currencies: list[str],
        provider: ExternalIntegrationId = ExternalIntegrationId.COINGECKO,
    ) -> CryptoAssetDetails:
        if provider == ExternalIntegrationId.COINGECKO:
            try:
                return await self._coingecko_client.get_asset_details(
                    provider_id=provider_id, currencies=currencies
                )
            except Exception as e:
                self._log.warning(
                    f"CoinGecko live asset details failed for {provider_id}, "
                    f"falling back to cloud dataset: {e}"
                )
                details = await self._coingecko_snapshot_details(
                    provider_id, currencies
                )
                if details is not None:
                    return details
                raise
        if provider == ExternalIntegrationId.COINMARKETCAP:
            details = await self._cmc_client.get_asset_details(provider_id, currencies)
            if details is not None:
                return details
            raise ValueError(
                f"CoinMarketCap asset details unavailable for {provider_id}"
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

    async def _safe_cg_dataset(
        self, max_age: timedelta = CryptoDatasetClient.LIST_MAX_AGE
    ) -> Optional[CryptoDataset]:
        try:
            return await self._dataset_client.load_coingecko(max_age=max_age)
        except Exception as e:
            self._log.warning(f"CoinGecko cloud dataset unavailable: {e}")
            return None

    async def _coingecko_snapshot_prices(
        self, symbols: list[str], fiat_isos: list[str]
    ) -> dict[str, dict[str, Dezimal]]:
        dataset = await self._safe_cg_dataset(CryptoDatasetClient.PRICE_MAX_AGE)
        if dataset is None:
            return {}
        return dataset.prices_by_symbols(symbols, fiat_isos)

    async def _coingecko_snapshot_details(
        self, provider_id: str, currencies: list[str]
    ) -> Optional[CryptoAssetDetails]:
        dataset = await self._safe_cg_dataset()
        if dataset is None:
            return None
        coin = dataset.coin_by_id(provider_id)
        if coin is None:
            return None

        platforms_index: dict[str, CryptoPlatform] = {}
        try:
            platforms_index = await self._coingecko_client.get_asset_platforms()
        except Exception:
            platforms_index = {}

        enriched_platforms: list[CryptoAssetPlatform] = []
        for platform_id, contract_address in coin.platforms.items():
            if not platform_id or not contract_address:
                continue
            platform_info = platforms_index.get(platform_id)
            enriched_platforms.append(
                CryptoAssetPlatform(
                    provider_id=platform_id,
                    name=platform_info.name if platform_info else platform_id,
                    contract_address=contract_address,
                    icon_url=platform_info.icon_url if platform_info else None,
                    related_entity_id=None,
                )
            )

        wanted = [currency.upper() for currency in currencies]
        price_map = {cur: coin.prices[cur] for cur in wanted if cur in coin.prices}

        return CryptoAssetDetails(
            name=coin.name,
            symbol=coin.symbol.upper(),
            platforms=enriched_platforms,
            provider=ExternalIntegrationId.COINGECKO,
            provider_id=coin.id,
            price=price_map,
            icon_url=coin.icon_url,
            type=CryptoCurrencyType.TOKEN
            if enriched_platforms
            else CryptoCurrencyType.NATIVE,
        )

    @staticmethod
    def _missing_addresses(
        addresses: list[str], result: dict[str, dict[str, Dezimal]]
    ) -> list[str]:
        missing: list[str] = []
        for address in addresses:
            if not isinstance(address, str):
                continue
            if address.strip().lower() not in result:
                missing.append(address)
        return missing
