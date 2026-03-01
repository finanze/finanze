from dataclasses import field
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.dezimal import Dezimal
from domain.external_integration import (
    EnabledExternalIntegrations,
    ExternalIntegrationId,
)
from domain.public_key import ScriptType, CoinType


class CryptoCurrencyType(str, Enum):
    NATIVE = "NATIVE"
    TOKEN = "TOKEN"


@dataclass
class CryptoAsset:
    name: str
    symbol: Optional[str]
    icon_urls: Optional[list[str]]
    external_ids: dict[str, str]
    id: Optional[UUID] = None


@dataclass
class HDAddress:
    address: str
    index: int
    change: int
    path: str
    pubkey: str


@dataclass
class HDWallet:
    xpub: str
    addresses: list[HDAddress]
    script_type: ScriptType
    coin_type: CoinType


class AddressSource(str, Enum):
    DERIVED = "DERIVED"
    MANUAL = "MANUAL"


@dataclass
class CryptoWallet:
    id: UUID
    entity_id: UUID
    addresses: list[str]
    name: str
    address_source: AddressSource
    hd_wallet: Optional[HDWallet]


@dataclass
class CryptoFetchRequest:
    integrations: EnabledExternalIntegrations
    addresses: list[str] = field(default_factory=list)
    txs: bool = False


@dataclass
class CryptoFetchedPosition:
    id: Optional[UUID]
    symbol: str
    balance: Dezimal
    type: CryptoCurrencyType
    name: Optional[str] = None
    contract_address: Optional[str] = None


@dataclass
class CryptoFetchResult:
    address: str
    assets: list[CryptoFetchedPosition] = field(default_factory=list)
    has_txs: Optional[bool] = None


@dataclass
class CryptoFetchResults:
    results: dict[str, Optional[CryptoFetchResult]]

    @staticmethod
    def _asset_key(asset: CryptoFetchedPosition) -> tuple:
        if asset.type == CryptoCurrencyType.TOKEN and asset.contract_address:
            return asset.type, asset.contract_address
        return asset.type, asset.symbol

    @staticmethod
    def _merge_results(
        existing: CryptoFetchResult, incoming: CryptoFetchResult
    ) -> None:
        existing_assets = {
            CryptoFetchResults._asset_key(asset): asset for asset in existing.assets
        }
        for asset in incoming.assets:
            key = CryptoFetchResults._asset_key(asset)
            if key in existing_assets:
                existing_assets[key].balance += asset.balance
            else:
                existing_assets[key] = asset
        existing.assets = list(existing_assets.values())
        if incoming.has_txs is not None:
            existing.has_txs = existing.has_txs or incoming.has_txs

    def __add__(self, other: CryptoFetchResults) -> CryptoFetchResults:
        combined_results = self.results.copy()
        for address, result in other.results.items():
            if address not in combined_results or combined_results[address] is None:
                combined_results[address] = result
            elif result is not None:
                self._merge_results(combined_results[address], result)
        return CryptoFetchResults(results=combined_results)


@dataclass
class ConnectCryptoWallet:
    entity_id: UUID
    addresses: list[str]
    name: str
    address_source: AddressSource
    xpub: Optional[str] = None
    script_type: ScriptType | None = None


class CryptoWalletConnectionFailureCode(str, Enum):
    ADDRESS_ALREADY_EXISTS = "ADDRESS_ALREADY_EXISTS"
    ADDRESS_NOT_FOUND = "ADDRESS_NOT_FOUND"
    XPUB_ALREADY_EXISTS = "XPUB_ALREADY_EXISTS"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


@dataclass
class CryptoWalletConnectionResult:
    failed: dict[str, CryptoWalletConnectionFailureCode]


@dataclass
class UpdateCryptoWalletConnection:
    id: UUID
    name: str


@dataclass
class CryptoPlatform:
    provider_id: str
    name: str
    icon_url: Optional[str]


@dataclass
class CryptoAssetPlatform:
    provider_id: str
    name: str
    contract_address: Optional[str]
    icon_url: Optional[str]
    related_entity_id: Optional[UUID]


@dataclass
class AvailableCryptoAsset:
    name: str
    symbol: str
    platforms: list[CryptoAssetPlatform]
    provider: ExternalIntegrationId
    provider_id: str


@dataclass
class AvailableCryptoAssets:
    assets: list[AvailableCryptoAsset]


@dataclass
class AvailableCryptoAssetsRequest:
    symbol: Optional[str]
    name: Optional[str]
    page: int = 1
    limit: int = 50


@dataclass
class AvailableCryptoAssetsResult:
    provider: ExternalIntegrationId
    assets: list[AvailableCryptoAsset]
    page: int
    limit: int
    total: int


@dataclass
class CryptoAssetDetails:
    name: str
    symbol: str
    platforms: list[CryptoAssetPlatform]
    provider: ExternalIntegrationId
    provider_id: str
    price: dict[str, Dezimal]
    type: CryptoCurrencyType
    icon_url: Optional[str]
