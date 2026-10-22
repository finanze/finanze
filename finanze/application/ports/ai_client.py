import abc
from typing import Optional

from application.ports.connectable_integration import ConnectableIntegration
from domain.ai import (
    AIClientFeature,
    AIDecisionRequest,
    AIDecisionResult,
    AIGeneration,
    AIGenerationRequest,
    AIModel,
    AIModelProvider,
    AIServerInfo,
)
from domain.exception.exceptions import AIProviderError, AIProviderErrorCode
from domain.external_integration import ExternalIntegrationPayload


class AIClient(ConnectableIntegration, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def features(self) -> set[AIClientFeature]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_model(
        self, model_id: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[AIModel]:
        raise NotImplementedError

    @abc.abstractmethod
    async def generate(
        self, request: AIGenerationRequest, credentials: ExternalIntegrationPayload
    ) -> AIGeneration:
        raise NotImplementedError

    async def get_model_providers(
        self, model_id: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[list[AIModelProvider]]:
        raise AIProviderError(
            AIProviderErrorCode.UNSUPPORTED_OPERATION, "Model providers not supported"
        )

    async def list_models(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> list[AIModel]:
        raise AIProviderError(
            AIProviderErrorCode.UNSUPPORTED_OPERATION, "Model listing not supported"
        )

    async def decide(
        self, request: AIDecisionRequest, credentials: ExternalIntegrationPayload
    ) -> AIDecisionResult:
        raise AIProviderError(
            AIProviderErrorCode.UNSUPPORTED_OPERATION, "Decisions not supported"
        )

    async def get_server_info(
        self, credentials: ExternalIntegrationPayload
    ) -> AIServerInfo:
        raise AIProviderError(
            AIProviderErrorCode.UNSUPPORTED_OPERATION, "Server info not supported"
        )
