import logging
from typing import Optional

from application.ports.ai_client import AIClient
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.ai import (
    AIClientFeature,
    AIModelCapability,
    AIModelProvider,
    AIModelValidation,
    ValidateAIModelRequest,
    supports_task,
)
from domain.exception.exceptions import AIProviderError, IntegrationNotFound
from domain.external_integration import (
    ExternalIntegrationId,
    ExternalIntegrationPayload,
)
from domain.use_cases.validate_ai_model import ValidateAIModel

MAX_MODEL_ID_LENGTH = 200


class ValidateAIModelImpl(ValidateAIModel):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        clients: dict[ExternalIntegrationId, AIClient],
    ):
        self._external_integration_port = external_integration_port
        self._clients = clients
        self._log = logging.getLogger(__name__)

    async def execute(self, request: ValidateAIModelRequest) -> AIModelValidation:
        client = self._clients.get(request.provider)
        if client is None:
            raise IntegrationNotFound()

        model_id = (request.model or "").strip()
        if not model_id or len(model_id) > MAX_MODEL_ID_LENGTH:
            return AIModelValidation(valid=False)

        features = client.features()
        upstream = (request.upstream_provider or "").strip() or None
        if upstream and (
            AIClientFeature.UPSTREAM_PROVIDERS not in features
            or len(upstream) > MAX_MODEL_ID_LENGTH
        ):
            return AIModelValidation(valid=False)

        credentials = await self._external_integration_port.get_payload(
            request.provider
        )
        try:
            model = await client.get_model(model_id, credentials)
        except AIProviderError as e:
            self._log.warning(f"Could not fetch AI model {model_id}: {e.details}")
            return AIModelValidation(valid=False)
        if model is None:
            return AIModelValidation(valid=False)

        capabilities = set(model.capabilities)
        if AIClientFeature.DECISIONS not in features:
            capabilities.discard(AIModelCapability.DECISIONS)

        matched_upstream = None
        if upstream:
            matched_upstream = await self._match_upstream(
                client, model_id, upstream, capabilities, request, credentials
            )
            if matched_upstream is None:
                return AIModelValidation(valid=False, name=model.name)
            capabilities &= matched_upstream.capabilities

        return AIModelValidation(
            valid=supports_task(capabilities, request.task),
            name=model.name,
            capabilities=sorted(capabilities, key=lambda c: c.value),
            upstream_provider=matched_upstream.id if matched_upstream else None,
        )

    async def _match_upstream(
        self,
        client: AIClient,
        model_id: str,
        upstream: str,
        capabilities: set[AIModelCapability],
        request: ValidateAIModelRequest,
        credentials: Optional[ExternalIntegrationPayload],
    ) -> Optional[AIModelProvider]:
        try:
            providers = await client.get_model_providers(model_id, credentials)
        except AIProviderError as e:
            self._log.warning(
                f"Could not fetch AI model providers for {model_id}: {e.details}"
            )
            return None
        return next(
            (
                provider
                for provider in providers or []
                if provider.matches(upstream)
                and supports_task(capabilities & provider.capabilities, request.task)
            ),
            None,
        )
