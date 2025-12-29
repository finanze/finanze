from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.dezimal import Dezimal
from domain.external_integration import (
    EnabledExternalIntegrations,
    ExternalIntegrationId,
)


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
class CryptoWalletConnection:
    id: UUID
    entity_id: UUID
    address: str
    name: str


@dataclass
class CryptoFetchRequest:
    address: str
    integrations: EnabledExternalIntegrations
    connection_id: Optional[UUID] = None


@dataclass
class ConnectCryptoWallet:
    entity_id: UUID
    addresses: list[str]
    name: str


class CryptoWalletConnectionFailureCode(str, Enum):
    ADDRESS_ALREADY_EXISTS = "ADDRESS_ALREADY_EXISTS"
    ADDRESS_NOT_FOUND = "ADDRESS_NOT_FOUND"
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
