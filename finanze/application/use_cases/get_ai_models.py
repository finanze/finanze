from typing import Optional

from application.ports.ai_client import AIClient
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.ai import (
    AICatalogModel,
    AIClientFeature,
    AIModel,
    AIModelCapability,
    AIModels,
    AITask,
    supports_task,
)
from domain.exception.exceptions import (
    ExternalIntegrationRequired,
    IntegrationNotFound,
)
from domain.external_integration import ExternalIntegrationId
from domain.use_cases.get_ai_models import GetAIModels


def _to_catalog_model(
    model: AIModel, features: set[AIClientFeature], task: Optional[AITask]
) -> AICatalogModel:
    capabilities = set(model.capabilities)
    if AIClientFeature.DECISIONS not in features:
        capabilities.discard(AIModelCapability.DECISIONS)
    return AICatalogModel(
        id=model.id,
        name=model.name,
        probabilistic=AIModelCapability.DECISIONS in capabilities,
        size=model.size,
        loaded=model.loaded,
        load_failed=model.load_failed,
        pricing=model.pricing,
        input_modalities=(
            sorted(model.input_modalities, key=lambda modality: modality.value)
            if model.input_modalities is not None
            else None
        ),
        eligible=supports_task(capabilities, task) if task else None,
    )


class GetAIModelsImpl(GetAIModels):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        clients: dict[ExternalIntegrationId, AIClient],
    ):
        self._external_integration_port = external_integration_port
        self._clients = clients

    async def execute(self, provider_id: str, task: Optional[AITask]) -> AIModels:
        try:
            integration_id = ExternalIntegrationId(provider_id)
        except ValueError:
            raise IntegrationNotFound()
        client = self._clients.get(integration_id)
        if client is None:
            raise IntegrationNotFound()
        features = client.features()
        if AIClientFeature.MODEL_LISTING not in features:
            return AIModels(models=[])

        credentials = await self._external_integration_port.get_payload(integration_id)
        if credentials is None:
            raise ExternalIntegrationRequired([integration_id])

        models = await client.list_models(credentials)
        return AIModels(
            models=[_to_catalog_model(model, features, task) for model in models]
        )
