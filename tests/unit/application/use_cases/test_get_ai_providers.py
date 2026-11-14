from unittest.mock import AsyncMock, MagicMock

import pytest
from application.use_cases.get_ai_providers import GetAIProvidersImpl
from domain.ai import AIClientFeature, AITask
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.ai.ai_model_presets import AI_MODEL_PRESETS

OPENAI = ExternalIntegrationId.OPENAI
LOCAL = ExternalIntegrationId.LOCAL_MODELS


def _client(*features: AIClientFeature) -> MagicMock:
    client = MagicMock()
    client.features.return_value = {AIClientFeature.GENERATION, *features}
    return client


def _use_case() -> GetAIProvidersImpl:
    integrations = AsyncMock()
    integrations.get_payload = AsyncMock(
        side_effect=lambda provider: {"api_key": "k"} if provider == OPENAI else None
    )
    clients = {
        OPENAI: _client(AIClientFeature.CUSTOM_MODELS, AIClientFeature.ATTACHMENTS),
        LOCAL: _client(AIClientFeature.MODEL_LISTING),
    }
    return GetAIProvidersImpl(integrations, clients, AI_MODEL_PRESETS)


class TestGetAIProviders:
    @pytest.mark.asyncio
    async def test_describes_every_ai_client(self):
        result = await _use_case().execute(None)

        openai, local = result.providers
        assert (openai.id, openai.connected, openai.custom_models) == (
            OPENAI,
            True,
            True,
        )
        assert (openai.dynamic_models, openai.attachments) == (False, True)
        assert (local.id, local.connected, local.dynamic_models) == (LOCAL, False, True)
        assert (local.custom_models, local.attachments) == (False, False)

    @pytest.mark.asyncio
    async def test_without_task_lists_all_presets_with_unknown_eligibility(self):
        openai = (await _use_case().execute(None)).providers[0]

        assert [(m.id, m.eligible) for m in openai.recommended_models] == [
            ("gpt-6-luna", None)
        ]

    @pytest.mark.asyncio
    async def test_task_keeps_only_its_presets(self):
        labeling = (await _use_case().execute(AITask.LABELING)).providers[0]
        importing = (await _use_case().execute(AITask.IMPORTING)).providers[0]

        assert [(m.id, m.eligible) for m in labeling.recommended_models] == [
            ("gpt-6-luna", True)
        ]
        assert importing.recommended_models == []
        assert AI_MODEL_PRESETS[OPENAI][0].model.eligible is None
