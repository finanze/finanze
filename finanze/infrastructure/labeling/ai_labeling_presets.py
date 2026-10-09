from dataclasses import dataclass
from typing import Optional

from domain.ai import AIReasoningEffort
from domain.external_integration import ExternalIntegrationId
from domain.external_labeling import ExternalLabelingModel


@dataclass(frozen=True)
class AILabelingPreset:
    model: ExternalLabelingModel
    reasoning_effort: Optional[AIReasoningEffort] = None


LABELING_PRESETS: dict[ExternalIntegrationId, list[AILabelingPreset]] = {
    ExternalIntegrationId.OPENROUTER: [
        AILabelingPreset(
            model=ExternalLabelingModel(
                id="~typesafe/jev-latest",
                name="Jev (latest)",
                description="TypeSafe decision model, returns calibrated probabilities",
                probabilistic=True,
            ),
        ),
    ],
    ExternalIntegrationId.OPENAI: [
        AILabelingPreset(
            model=ExternalLabelingModel(
                id="gpt-6-luna",
                name="GPT-6 Luna",
                description="Fast and low cost OpenAI model",
            ),
            reasoning_effort=AIReasoningEffort.NONE,
        ),
    ],
}
