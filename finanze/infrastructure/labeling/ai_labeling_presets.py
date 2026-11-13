from dataclasses import dataclass
from typing import Optional

from domain.ai import AIModelPreset, AIReasoningEffort, AITask
from domain.external_integration import ExternalIntegrationId
from domain.external_labeling import ExternalLabelingModel
from infrastructure.client.ai.ai_model_presets import AI_MODEL_PRESETS


@dataclass(frozen=True)
class AILabelingPreset:
    model: ExternalLabelingModel
    reasoning_effort: Optional[AIReasoningEffort] = None


def _labeling_preset(preset: AIModelPreset) -> AILabelingPreset:
    return AILabelingPreset(
        model=ExternalLabelingModel(
            id=preset.model.id,
            name=preset.model.name,
            description=preset.model.description,
            probabilistic=preset.model.probabilistic,
        ),
        reasoning_effort=preset.reasoning_effort,
    )


LABELING_PRESETS: dict[ExternalIntegrationId, list[AILabelingPreset]] = {
    integration_id: [
        _labeling_preset(preset)
        for preset in presets
        if AITask.LABELING in preset.tasks
    ]
    for integration_id, presets in AI_MODEL_PRESETS.items()
}

LABELING_BATCH_SIZES: dict[ExternalIntegrationId, int] = {
    ExternalIntegrationId.OPENAI_COMPATIBLE: 10,
    ExternalIntegrationId.LOCAL_MODELS: 10,
}
