from dataclasses import replace
from typing import Optional

from application.ports.ai_client import AIClient
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.ai import (
    AIClientFeature,
    AIModelPreset,
    AIProviderDetails,
    AIProviders,
    AITask,
)
from domain.external_integration import ExternalIntegrationId
from domain.use_cases.get_ai_providers import GetAIProviders


class GetAIProvidersImpl(GetAIProviders):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        clients: dict[ExternalIntegrationId, AIClient],
        presets: dict[ExternalIntegrationId, list[AIModelPreset]],
    ):
        self._external_integration_port = external_integration_port
        self._clients = clients
        self._presets = presets

    async def execute(self, task: Optional[AITask]) -> AIProviders:
        details = []
        for provider_id, client in self._clients.items():
            features = client.features()
            payload = await self._external_integration_port.get_payload(provider_id)
            details.append(
                AIProviderDetails(
                    id=provider_id,
                    connected=payload is not None,
                    recommended_models=[
                        replace(
                            preset.model,
                            eligible=task in preset.tasks if task else None,
                        )
                        for preset in self._presets.get(provider_id, [])
                        if task is None or task in preset.tasks
                    ],
                    custom_models=AIClientFeature.CUSTOM_MODELS in features,
                    upstream_providers=AIClientFeature.UPSTREAM_PROVIDERS in features,
                    dynamic_models=AIClientFeature.MODEL_LISTING in features,
                    attachments=AIClientFeature.ATTACHMENTS in features,
                )
            )
        return AIProviders(providers=details)
