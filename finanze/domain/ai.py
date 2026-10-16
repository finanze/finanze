from dataclasses import field
from enum import Enum
from typing import Optional

from domain.dezimal import Dezimal
from domain.external_integration import ExternalIntegrationId
from pydantic.dataclasses import dataclass


class AIClientFeature(str, Enum):
    GENERATION = "GENERATION"
    DECISIONS = "DECISIONS"
    UPSTREAM_PROVIDERS = "UPSTREAM_PROVIDERS"


class AIModelCapability(str, Enum):
    STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT"
    TEMPERATURE = "TEMPERATURE"
    REASONING = "REASONING"
    DECISIONS = "DECISIONS"


class AIReasoningEffort(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTRA_HIGH = "EXTRA_HIGH"


class AIMessageRole(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class AIGenerationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INCOMPLETE = "INCOMPLETE"
    REFUSED = "REFUSED"


class AITask(str, Enum):
    LABELING = "LABELING"


AI_TASK_REQUIREMENTS: dict[AITask, list[set[AIModelCapability]]] = {
    AITask.LABELING: [
        {AIModelCapability.DECISIONS},
        {AIModelCapability.STRUCTURED_OUTPUT},
    ],
}


def supports_task(capabilities: set[AIModelCapability], task: AITask) -> bool:
    return any(required <= capabilities for required in AI_TASK_REQUIREMENTS[task])


@dataclass
class AIModel:
    id: str
    name: str
    capabilities: set[AIModelCapability] = field(default_factory=set)


@dataclass
class AIModelProvider:
    id: str
    capabilities: set[AIModelCapability] = field(default_factory=set)

    def matches(self, name: str) -> bool:
        tag = self.id.casefold()
        return name.casefold() in (tag, tag.split("/")[0])


@dataclass
class ValidateAIModelRequest:
    provider: ExternalIntegrationId
    model: str
    task: AITask
    upstream_provider: Optional[str] = None


@dataclass
class AIModelValidation:
    valid: bool
    name: Optional[str] = None
    capabilities: list[AIModelCapability] = field(default_factory=list)
    upstream_provider: Optional[str] = None


@dataclass
class AIMessage:
    role: AIMessageRole
    content: str


@dataclass
class AIJsonSchema:
    name: str
    schema: dict


@dataclass
class AIGenerationRequest:
    model: str
    messages: list[AIMessage]
    instructions: Optional[str] = None
    response_schema: Optional[AIJsonSchema] = None
    temperature: Optional[Dezimal] = None
    reasoning_effort: Optional[AIReasoningEffort] = None
    max_output_tokens: Optional[int] = None
    upstream_provider: Optional[str] = None


@dataclass
class AIUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class AIGeneration:
    status: AIGenerationStatus
    text: Optional[str] = None
    refusal: Optional[str] = None
    usage: Optional[AIUsage] = None


@dataclass
class AIChoiceQuestion:
    id: str
    instructions: str
    options: list[str]


@dataclass
class AIDecisionRequest:
    model: str
    state: dict
    questions: list[AIChoiceQuestion]


@dataclass
class AIDecisionAnswer:
    choice: Optional[str] = None
    confidence: Optional[Dezimal] = None
    probabilities: dict[str, Dezimal] = field(default_factory=dict)


@dataclass
class AIDecisionResult:
    answers: dict[str, AIDecisionAnswer]
