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
    MODEL_LISTING = "MODEL_LISTING"
    CUSTOM_MODELS = "CUSTOM_MODELS"
    SERVER_INFO = "SERVER_INFO"
    ATTACHMENTS = "ATTACHMENTS"


class AIInputModality(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    DOCUMENT = "DOCUMENT"


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
    IMPORTING = "IMPORTING"


AI_TASK_REQUIREMENTS: dict[AITask, list[set[AIModelCapability]]] = {
    AITask.LABELING: [
        {AIModelCapability.DECISIONS},
        {AIModelCapability.STRUCTURED_OUTPUT},
    ],
    AITask.IMPORTING: [
        {AIModelCapability.STRUCTURED_OUTPUT},
    ],
}


def supports_task(capabilities: set[AIModelCapability], task: AITask) -> bool:
    return any(required <= capabilities for required in AI_TASK_REQUIREMENTS[task])


@dataclass
class AIModelPricing:
    input_per_million: Dezimal
    output_per_million: Dezimal
    currency: str = "USD"


@dataclass
class AIVisionLimits:
    max_images: Optional[int] = None
    max_image_bytes: Optional[int] = None
    max_image_pixels: Optional[int] = None
    media_types: Optional[list[str]] = None


@dataclass
class AIModel:
    id: str
    name: str
    capabilities: set[AIModelCapability] = field(default_factory=set)
    size: Optional[int] = None
    loaded: bool = False
    load_failed: bool = False
    pricing: Optional[AIModelPricing] = None
    # None means the provider does not report which inputs the model accepts.
    input_modalities: Optional[set[AIInputModality]] = None
    vision_limits: Optional[AIVisionLimits] = None


@dataclass
class AICatalogModel:
    id: str
    name: str
    description: Optional[str] = None
    probabilistic: bool = False
    size: Optional[int] = None
    loaded: bool = False
    load_failed: bool = False
    pricing: Optional[AIModelPricing] = None
    input_modalities: Optional[list[AIInputModality]] = None
    eligible: Optional[bool] = None


@dataclass
class AIModelPreset:
    model: AICatalogModel
    tasks: set[AITask] = field(default_factory=set)
    reasoning_effort: Optional[AIReasoningEffort] = None


@dataclass
class AIProviderDetails:
    id: ExternalIntegrationId
    connected: bool
    recommended_models: list[AICatalogModel] = field(default_factory=list)
    custom_models: bool = True
    upstream_providers: bool = False
    dynamic_models: bool = False
    attachments: bool = False


@dataclass
class AIProviders:
    providers: list[AIProviderDetails]


@dataclass
class AIModels:
    models: list[AICatalogModel]


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


class AIServerKind(str, Enum):
    OLLAMA = "OLLAMA"
    LM_STUDIO = "LM_STUDIO"
    LLAMA_CPP = "LLAMA_CPP"
    VLLM = "VLLM"


class AIServerError(str, Enum):
    UNREACHABLE = "UNREACHABLE"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    SERVER_ERROR = "SERVER_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"


@dataclass
class AIServerModel:
    id: str
    decisions: bool = False
    loaded: Optional[bool] = None
    size: Optional[int] = None
    context_length: Optional[int] = None


@dataclass
class AIServerInfo:
    url: str
    api_key_set: bool
    reachable: bool = False
    error: Optional[AIServerError] = None
    latency_ms: Optional[int] = None
    kind: Optional[AIServerKind] = None
    version: Optional[str] = None
    models: list[AIServerModel] = field(default_factory=list)


@dataclass
class AIAttachment:
    mime_type: str
    data: bytes
    name: Optional[str] = None


@dataclass
class AIMessage:
    role: AIMessageRole
    content: str
    attachments: list[AIAttachment] = field(default_factory=list)


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
