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
    address: str
    name: str


@dataclass
class UpdateCryptoWalletConnection:
    id: UUID
    name: str
