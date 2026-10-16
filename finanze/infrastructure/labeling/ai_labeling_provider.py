import logging
from typing import Optional
from uuid import UUID

from application.ports.ai_client import AIClient
from application.ports.external_tx_labeling_provider import (
    ExternalTxLabelingProvider,
)
from domain.ai import (
    AIClientFeature,
    AIGenerationStatus,
    AIModel,
    AIModelCapability,
    AIReasoningEffort,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import AIProviderError, ExternalLabelingUnavailable
from domain.external_integration import ExternalIntegrationPayload
from domain.external_labeling import (
    ExternalLabelingModel,
    ExternalLabelingRequest,
    ExternalLabelingTx,
    ExternalLabelSuggestion,
)
from infrastructure.labeling.ai_labeling_payloads import (
    build_decision_request,
    build_examples,
    build_generation_request,
    build_options,
    parse_decision,
    parse_generation,
)
from infrastructure.labeling.ai_labeling_presets import AILabelingPreset

DECISIONS_BATCH_SIZE = 12
GENERATION_BATCH_SIZE = 25


class AILabelingProvider(ExternalTxLabelingProvider):
    def __init__(self, client: AIClient, presets: list[AILabelingPreset]):
        self._client = client
        self._presets = {preset.model.id: preset for preset in presets}
        self._model_cache: dict[str, AIModel] = {}
        self._log = logging.getLogger(__name__)

    def get_recommended_models(self) -> list[ExternalLabelingModel]:
        return [preset.model for preset in self._presets.values()]

    def supports_upstream_providers(self) -> bool:
        return AIClientFeature.UPSTREAM_PROVIDERS in self._client.features()

    async def label(
        self,
        request: ExternalLabelingRequest,
        credentials: ExternalIntegrationPayload,
    ) -> list[ExternalLabelSuggestion]:
        if not request.txs or not request.labels:
            return []

        option_ids, descriptions = build_options(request.labels)
        options_by_label = {label_id: option for option, label_id in option_ids.items()}
        examples = build_examples(request.examples, options_by_label)

        info = await self._model_info(request.model, credentials)
        preset = self._presets.get(request.model)
        if info is not None:
            use_decisions = self._uses_decisions(info)
        else:
            use_decisions = (
                preset is not None
                and preset.model.probabilistic
                and AIClientFeature.DECISIONS in self._client.features()
            )
        temperature = (
            Dezimal(0)
            if info is not None and AIModelCapability.TEMPERATURE in info.capabilities
            else None
        )
        reasoning_effort = preset.reasoning_effort if preset else None

        batch_size = DECISIONS_BATCH_SIZE if use_decisions else GENERATION_BATCH_SIZE
        suggestions = []
        try:
            for index in range(0, len(request.txs), batch_size):
                batch = request.txs[index : index + batch_size]
                if use_decisions:
                    result = await self._client.decide(
                        build_decision_request(
                            request.model,
                            batch,
                            descriptions,
                            examples,
                            request.instructions,
                        ),
                        credentials,
                    )
                    suggestions += parse_decision(result, batch, option_ids)
                else:
                    suggestions += await self._generate(
                        request,
                        batch,
                        option_ids,
                        descriptions,
                        examples,
                        temperature,
                        reasoning_effort,
                        credentials,
                    )
        except AIProviderError as e:
            raise ExternalLabelingUnavailable(e.details) from e
        return suggestions

    async def _generate(
        self,
        request: ExternalLabelingRequest,
        batch: list[ExternalLabelingTx],
        option_ids: dict[str, UUID],
        descriptions: dict[str, str],
        examples: list[dict],
        temperature: Optional[Dezimal],
        reasoning_effort: Optional[AIReasoningEffort],
        credentials: ExternalIntegrationPayload,
    ) -> list[ExternalLabelSuggestion]:
        generation = await self._client.generate(
            build_generation_request(
                request.model,
                batch,
                descriptions,
                examples,
                request.instructions,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
                upstream_provider=request.upstream_provider,
            ),
            credentials,
        )
        if generation.status != AIGenerationStatus.COMPLETED or not generation.text:
            self._log.warning(
                f"AI labeling generation for {request.model} ended with status {generation.status.value}"
            )
            return []
        suggestions = parse_generation(generation.text, batch, option_ids)
        if suggestions is None:
            self._log.warning(
                f"AI labeling generation for {request.model} returned non JSON content"
            )
            return []
        return suggestions

    def _uses_decisions(self, info: AIModel) -> bool:
        return (
            AIModelCapability.DECISIONS in info.capabilities
            and AIClientFeature.DECISIONS in self._client.features()
        )

    async def _model_info(
        self, model: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[AIModel]:
        if model in self._model_cache:
            return self._model_cache[model]
        try:
            info = await self._client.get_model(model, credentials)
        except Exception:
            self._log.warning(f"Could not fetch AI model info for {model}")
            return None
        if info is not None:
            self._model_cache[model] = info
        return info
