import abc
from typing import Optional

from domain.crypto import (
    AvailableCryptoAsset,
    CryptoAsset,
    CryptoAssetDetails,
    CryptoPlatform,
)
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.external_integration import ExternalIntegrationId


class CryptoAssetInfoProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_price(self, symbol: str, fiat_iso: str, **kwargs) -> Dezimal:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_multiple_prices_by_symbol(
        self, symbols: list[str], fiat_isos: list[str], **kwargs
    ) -> dict[str, dict[str, Dezimal]]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_prices_by_addresses(
        self, addresses: list[str], fiat_isos: list[str], **kwargs
    ) -> dict[str, dict[str, Dezimal]]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_symbol(self, symbol: str) -> list[CryptoAsset]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_multiple_overview_by_addresses(
        self, addresses: list[str]
    ) -> dict[str, CryptoAsset]:
        raise NotImplementedError

    @abc.abstractmethod
    async def asset_lookup(
        self, symbol: str | None = None, name: str | None = None
    ) -> list[AvailableCryptoAsset]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_asset_platforms(self) -> dict[str, CryptoPlatform]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_asset_details(
        self,
        provider_id: str,
        currencies: list[str],
        provider: ExternalIntegrationId = ExternalIntegrationId.COINGECKO,
    ) -> CryptoAssetDetails:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_native_entity_by_platform(
        self, provider_id: str, provider: ExternalIntegrationId
    ) -> Optional[Entity]:
        raise NotImplementedError
