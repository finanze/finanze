from datetime import datetime
from enum import Enum
from typing import Optional

from domain.platform import IntegrationPlatform
from pydantic.dataclasses import dataclass


class ExternalIntegrationType(str, Enum):
    CRYPTO_PROVIDER = "CRYPTO_PROVIDER"
    DATA_SOURCE = "DATA_SOURCE"
    ENTITY_PROVIDER = "ENTITY_PROVIDER"
    CRYPTO_MARKET_PROVIDER = "CRYPTO_MARKET_PROVIDER"
    AI_PROVIDER = "AI_PROVIDER"


class ExternalIntegrationStatus(str, Enum):
    ON = "ON"
    OFF = "OFF"
    EXPIRED = "EXPIRED"


class ExternalIntegrationId(str, Enum):
    GOOGLE_SHEETS = "GOOGLE_SHEETS"
    ETHERSCAN = "ETHERSCAN"
    ETHPLORER = "ETHPLORER"
    ZERION = "ZERION"
    GOCARDLESS = "GOCARDLESS"
    ENABLE_BANKING = "ENABLE_BANKING"
    COINGECKO = "COINGECKO"
    COINMARKETCAP = "COINMARKETCAP"
    CRYPTOCOMPARE = "CRYPTOCOMPARE"
    OPENROUTER = "OPENROUTER"
    OPENAI = "OPENAI"
    OPENAI_COMPATIBLE = "OPENAI_COMPATIBLE"
    LOCAL_MODELS = "LOCAL_MODELS"
    GITHUB_COPILOT = "GITHUB_COPILOT"
    CLAUDE_AGENT = "CLAUDE_AGENT"
    CHATGPT = "CHATGPT"


class AIProviderFamily(str, Enum):
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    OPENROUTER = "OPENROUTER"
    GITHUB_COPILOT = "GITHUB_COPILOT"
    LOCAL_MODELS = "LOCAL_MODELS"
    CUSTOM = "CUSTOM"


AI_PROVIDER_FAMILIES = {
    ExternalIntegrationId.OPENAI: AIProviderFamily.OPENAI,
    ExternalIntegrationId.CHATGPT: AIProviderFamily.OPENAI,
    ExternalIntegrationId.CLAUDE_AGENT: AIProviderFamily.ANTHROPIC,
    ExternalIntegrationId.OPENROUTER: AIProviderFamily.OPENROUTER,
    ExternalIntegrationId.GITHUB_COPILOT: AIProviderFamily.GITHUB_COPILOT,
    ExternalIntegrationId.LOCAL_MODELS: AIProviderFamily.LOCAL_MODELS,
    ExternalIntegrationId.OPENAI_COMPATIBLE: AIProviderFamily.CUSTOM,
}

AI_PROVIDER_FAMILY_NAMES = {
    AIProviderFamily.OPENAI: "OpenAI",
    AIProviderFamily.ANTHROPIC: "Anthropic",
    AIProviderFamily.OPENROUTER: "OpenRouter",
    AIProviderFamily.GITHUB_COPILOT: "GitHub Copilot",
    AIProviderFamily.LOCAL_MODELS: "Local Models",
    AIProviderFamily.CUSTOM: "Custom AI",
}

AI_PROVIDER_PLATFORMS = {
    integration: tuple(
        platform
        for platform in IntegrationPlatform
        if platform != IntegrationPlatform.MOBILE
        or integration
        not in (
            ExternalIntegrationId.LOCAL_MODELS,
            ExternalIntegrationId.GITHUB_COPILOT,
            ExternalIntegrationId.CLAUDE_AGENT,
        )
    )
    for integration in AI_PROVIDER_FAMILIES
}


@dataclass
class ExternalIntegrationFamily:
    id: str
    name: str


@dataclass
class ExternalIntegration:
    id: ExternalIntegrationId
    name: str
    type: ExternalIntegrationType
    status: ExternalIntegrationStatus
    available: bool = True
    payload_schema: dict[str, str] | None = None
    optional_fields: list[str] | None = None
    family: Optional[ExternalIntegrationFamily] = None
    platforms: Optional[list[IntegrationPlatform]] = None


@dataclass
class AvailableExternalIntegrations:
    integrations: list[ExternalIntegration]


ExternalIntegrationPayload = dict[str, str]


@dataclass
class ConnectedExternalIntegrationRequest:
    integration_id: ExternalIntegrationId
    payload: ExternalIntegrationPayload
    completion_url: Optional[str] = None


@dataclass
class ExternalIntegrationDeviceAuthorization:
    flow_id: str
    user_code: str
    verification_uri: str
    expires_at: datetime
    interval: int


@dataclass
class ExternalIntegrationConnectionResult:
    link: Optional[str] = None
    device: Optional[ExternalIntegrationDeviceAuthorization] = None


class DeviceAuthorizationStatus(str, Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"


@dataclass
class DeviceAuthorizationPollResult:
    status: DeviceAuthorizationStatus
    interval: int
    payload: Optional[ExternalIntegrationPayload] = None


class ExternalIntegrationConnectionStatus(str, Enum):
    PENDING = "PENDING"
    CONNECTED = "CONNECTED"


@dataclass
class PollExternalIntegrationConnectionRequest:
    integration_id: ExternalIntegrationId
    flow_id: str


@dataclass
class ExternalIntegrationConnectionPoll:
    status: ExternalIntegrationConnectionStatus
    interval: Optional[int] = None


@dataclass
class CompleteExternalIntegrationConnectionRequest:
    integration_id: ExternalIntegrationId
    state: str
    code: Optional[str] = None
    error: Optional[str] = None
    client_id: Optional[str] = None


@dataclass
class ForwardIntegrationOAuthCallbackRequest:
    state: str
    code: Optional[str] = None
    error: Optional[str] = None
    client_id: Optional[str] = None


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
    ExternalIntegrationId.ZERION: {
        "api_key": "API Key",
    },
    ExternalIntegrationId.GOCARDLESS: {
        "secret_id": "Secret ID",
        "secret_key": "Secret Key",
    },
    ExternalIntegrationId.ENABLE_BANKING: {
        "application_id": "Application ID",
        "private_key": "Private Key (PEM)",
    },
    ExternalIntegrationId.OPENROUTER: {
        "api_key": "API Key",
    },
    ExternalIntegrationId.OPENAI: {
        "api_key": "API Key",
    },
    ExternalIntegrationId.OPENAI_COMPATIBLE: {
        "base_url": "Base URL",
        "api_key": "API Key",
    },
    ExternalIntegrationId.LOCAL_MODELS: {
        "server_url": "Server URL",
        "api_key": "API Key",
    },
    ExternalIntegrationId.GITHUB_COPILOT: {},
    ExternalIntegrationId.CLAUDE_AGENT: {
        "cli_path": "Claude Code path",
    },
    ExternalIntegrationId.CHATGPT: {},
}

EXTERNAL_INTEGRATION_OPTIONAL_FIELDS: dict[ExternalIntegrationId, set[str]] = {
    ExternalIntegrationId.OPENAI_COMPATIBLE: {"api_key"},
    ExternalIntegrationId.LOCAL_MODELS: {"server_url", "api_key"},
    ExternalIntegrationId.CLAUDE_AGENT: {"cli_path"},
}
