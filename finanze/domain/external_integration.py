from enum import Enum

from pydantic.dataclasses import dataclass


class ExternalIntegrationType(str, Enum):
    CRYPTO_PROVIDER = "CRYPTO_PROVIDER"
    DATA_SOURCE = "DATA_SOURCE"


class ExternalIntegrationStatus(str, Enum):
    ON = "ON"
    OFF = "OFF"


class ExternalIntegrationId(str, Enum):
    GOOGLE_SHEETS = "GOOGLE_SHEETS"
    ETHERSCAN = "ETHERSCAN"


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
