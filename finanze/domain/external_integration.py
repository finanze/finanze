from enum import Enum

from pydantic.dataclasses import dataclass


class ExternalIntegrationType(str, Enum):
    CRYPTO_PROVIDER = "CRYPTO_PROVIDER"
    DATA_SOURCE = "DATA_SOURCE"
    ENTITY_PROVIDER = "ENTITY_PROVIDER"


class ExternalIntegrationStatus(str, Enum):
    ON = "ON"
    OFF = "OFF"


class ExternalIntegrationId(str, Enum):
    GOOGLE_SHEETS = "GOOGLE_SHEETS"
    ETHERSCAN = "ETHERSCAN"
    GOCARDLESS = "GOCARDLESS"
    COINGECKO = "COINGECKO"
    CRYPTOCOMPARE = "CRYPTOCOMPARE"


@dataclass
class ExternalIntegration:
    id: ExternalIntegrationId
    name: str
    type: ExternalIntegrationType
    status: ExternalIntegrationStatus


@dataclass
class AvailableExternalIntegrations:
    integrations: list[ExternalIntegration]


@dataclass
class GoogleIntegrationCredentials:
    client_id: str
    client_secret: str


@dataclass
class EtherscanIntegrationData:
    api_key: str


@dataclass
class GoCardlessIntegrationCredentials:
    secret_id: str
    secret_key: str
