import logging
from datetime import timedelta
from typing import Optional

from domain.crypto import (
    AvailableCryptoAsset,
    CryptoAsset,
    CryptoAssetDetails,
    CryptoAssetPlatform,
    CryptoCurrencyType,
    CryptoPlatform,
)
from domain.dezimal import Dezimal
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.rates.crypto.crypto_dataset_client import (
    CryptoDataset,
    CryptoDatasetClient,
    CryptoDatasetCoin,
)


class CoinMarketCapDatasetClient:
    PROVIDER = ExternalIntegrationId.COINMARKETCAP

    def __init__(self, dataset_client: CryptoDatasetClient):
        self._dataset_client = dataset_client
        self._log = logging.getLogger(__name__)

    async def _dataset(
        self, max_age: timedelta = CryptoDatasetClient.LIST_MAX_AGE
    ) -> Optional[CryptoDataset]:
        try:
            return await self._dataset_client.load_coinmarketcap(max_age=max_age)
        except Exception as e:
            self._log.warning(f"Failed to load CoinMarketCap dataset: {e}")
            return None

    async def search(self, symbol: str) -> list[CryptoAsset]:
        if not symbol or not symbol.strip():
            return []
        dataset = await self._dataset()
        if dataset is None:
            return []
        return [self._to_crypto_asset(coin) for coin in dataset.coins_by_symbol(symbol)]

    async def asset_lookup(
        self, symbol: Optional[str] = None, name: Optional[str] = None
    ) -> list[AvailableCryptoAsset]:
        if not symbol and not name:
            return []
        dataset = await self._dataset()
        if dataset is None:
            return []
        query = (symbol or name or "").strip().lower()
        if not query:
            return []

        matches: list[AvailableCryptoAsset] = []
        for coin in dataset.coins:
            if symbol:
                if coin.symbol.lower().startswith(query):
                    matches.append(self._to_available_asset(coin, dataset))
            elif name:
                if coin.name.lower().startswith(query):
                    matches.append(self._to_available_asset(coin, dataset))
        return matches

    async def get_asset_platforms(self) -> dict[str, CryptoPlatform]:
        dataset = await self._dataset()
        if dataset is None:
            return {}
        return {
            platform_id: CryptoPlatform(
                provider_id=platform.provider_id,
                name=platform.name,
                icon_url=platform.icon_url,
            )
            for platform_id, platform in dataset.platforms.items()
        }

    async def get_prices(
        self, symbols: list[str], vs_currencies: list[str]
    ) -> dict[str, dict[str, Dezimal]]:
        if not symbols:
            return {}
        dataset = await self._dataset(CryptoDatasetClient.PRICE_MAX_AGE)
        if dataset is None:
            return {}
        return dataset.prices_by_symbols(symbols, vs_currencies)

    async def get_prices_by_addresses(
        self, addresses: list[str], vs_currencies: list[str]
    ) -> dict[str, dict[str, Dezimal]]:
        if not addresses:
            return {}
        dataset = await self._dataset(CryptoDatasetClient.PRICE_MAX_AGE)
        if dataset is None:
            return {}
        return dataset.prices_by_addresses(addresses, vs_currencies)

    async def get_asset_details(
        self, provider_id: str, currencies: list[str]
    ) -> Optional[CryptoAssetDetails]:
        dataset = await self._dataset()
        if dataset is None:
            return None
        coin = dataset.coin_by_id(provider_id)
        if coin is None:
            return None

        enriched_platforms: list[CryptoAssetPlatform] = []
        for platform_id, contract_address in coin.platforms.items():
            if not platform_id or not contract_address:
                continue
            platform_info = dataset.platforms.get(platform_id)
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
            provider=self.PROVIDER,
            provider_id=coin.id,
            price=price_map,
            type=CryptoCurrencyType.TOKEN
            if enriched_platforms
            else CryptoCurrencyType.NATIVE,
            icon_url=coin.icon_url,
        )

    def _to_crypto_asset(self, coin: CryptoDatasetCoin) -> CryptoAsset:
        icon_urls = [coin.icon_url] if coin.icon_url else None
        return CryptoAsset(
            name=coin.name,
            symbol=coin.symbol.upper(),
            icon_urls=icon_urls,
            external_ids={self.PROVIDER.value: coin.id},
        )

    def _to_available_asset(
        self, coin: CryptoDatasetCoin, dataset: CryptoDataset
    ) -> AvailableCryptoAsset:
        enriched_platforms: list[CryptoAssetPlatform] = []
        for platform_id, contract_address in coin.platforms.items():
            if not platform_id or not contract_address:
                continue
            platform_info = dataset.platforms.get(platform_id)
            enriched_platforms.append(
                CryptoAssetPlatform(
                    provider_id=platform_id,
                    name=platform_info.name if platform_info else platform_id,
                    contract_address=contract_address,
                    icon_url=platform_info.icon_url if platform_info else None,
                    related_entity_id=None,
                )
            )
        return AvailableCryptoAsset(
            name=coin.name,
            symbol=coin.symbol.upper(),
            platforms=enriched_platforms,
            provider=self.PROVIDER,
            provider_id=coin.id,
        )
