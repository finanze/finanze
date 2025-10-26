from enum import Enum
from typing import Optional
from uuid import UUID

from domain.external_integration import EtherscanIntegrationData
from pydantic.dataclasses import dataclass


@dataclass
class CryptoWalletConnection:
    id: UUID
    entity_id: UUID
    address: str
    name: str


@dataclass
class CryptoFetchIntegrations:
    etherscan: Optional[EtherscanIntegrationData] = None


@dataclass
class CryptoFetchRequest:
    address: str
    integrations: CryptoFetchIntegrations
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
