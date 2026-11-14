from domain.ai import AICatalogModel, AIModelPreset, AIReasoningEffort, AITask
from domain.external_integration import ExternalIntegrationId

AI_MODEL_PRESETS: dict[ExternalIntegrationId, list[AIModelPreset]] = {
    ExternalIntegrationId.OPENROUTER: [
        AIModelPreset(
            model=AICatalogModel(
                id="~typesafe/jev-latest",
                name="Jev (latest)",
                description="TypeSafe decision model, returns calibrated probabilities",
                probabilistic=True,
            ),
            tasks={AITask.LABELING},
        ),
    ],
    ExternalIntegrationId.OPENAI: [
        AIModelPreset(
            model=AICatalogModel(
                id="gpt-6-luna",
                name="GPT-6 Luna",
                description="Fast and low cost OpenAI decision model, returns calibrated probabilities",
                probabilistic=True,
            ),
            tasks={AITask.LABELING},
            reasoning_effort=AIReasoningEffort.NONE,
        ),
    ],
    ExternalIntegrationId.OPENAI_COMPATIBLE: [],
    ExternalIntegrationId.LOCAL_MODELS: [],
    ExternalIntegrationId.GITHUB_COPILOT: [],
    ExternalIntegrationId.CLAUDE_AGENT: [],
}
