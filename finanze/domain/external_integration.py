from enum import Enum

from pydantic.dataclasses import dataclass


class ExternalIntegrationType(str, Enum):
    CRYPTO_PROVIDER = "CRYPTO_PROVIDER"
    DATA_SOURCE = "DATA_SOURCE"
    ENTITY_PROVIDER = "ENTITY_PROVIDER"
    CRYPTO_MARKET_PROVIDER = "CRYPTO_MARKET_PROVIDER"


class ExternalIntegrationStatus(str, Enum):
    ON = "ON"
    OFF = "OFF"


class ExternalIntegrationId(str, Enum):
    GOOGLE_SHEETS = "GOOGLE_SHEETS"
    ETHERSCAN = "ETHERSCAN"
    ETHPLORER = "ETHPLORER"
    GOCARDLESS = "GOCARDLESS"
    COINGECKO = "COINGECKO"
    CRYPTOCOMPARE = "CRYPTOCOMPARE"


@dataclass
class ExternalIntegration:
    id: ExternalIntegrationId
    name: str
    type: ExternalIntegrationType
    status: ExternalIntegrationStatus
    available: bool = True
    payload_schema: dict[str, str] | None = None


@dataclass
class AvailableExternalIntegrations:
    integrations: list[ExternalIntegration]


ExternalIntegrationPayload = dict[str, str]


@dataclass
class ConnectedExternalIntegrationRequest:
    integration_id: ExternalIntegrationId
    payload: ExternalIntegrationPayload


@dataclass
class DisconnectedExternalIntegrationRequest:
    integration_id: ExternalIntegrationId


EnabledExternalIntegrations = dict[ExternalIntegrationId, ExternalIntegrationPayload]


EXTERNAL_INTEGRATION_PAYLOAD_SCHEMAS = {
    ExternalIntegrationId.GOOGLE_SHEETS: {
        "client_id": "Client ID",
        "client_secret": "Client Secret",
    },
    ExternalIntegrationId.ETHERSCAN: {
        "api_key": "API Key",
    },
    ExternalIntegrationId.ETHPLORER: {
        "api_key": "API Key",
    },
    ExternalIntegrationId.GOCARDLESS: {
        "secret_id": "Secret ID",
        "secret_key": "Secret Key",
    },
}
