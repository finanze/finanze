from typing import Optional
from urllib.parse import quote

from domain.ai import (
    AIClientFeature,
    AIDecisionRequest,
    AIDecisionResult,
    AIGeneration,
    AIGenerationRequest,
    AIModel,
    AIModelCapability,
    AIModelProvider,
)
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    TooManyRequests,
)
from domain.external_integration import ExternalIntegrationPayload
from infrastructure.client.ai.chat_completions import (
    chat_messages,
    decision_body,
    json_schema_format,
    parse_chat_completion,
    parse_decisions,
)
from infrastructure.client.ai.http_ai_client import (
    REASONING_EFFORTS,
    HttpAIClient,
)
from infrastructure.client.http.http_response import HttpResponse

APP_TITLE = "Finanze"
DECISIONS_OUTPUT = "decisions"
TEXT_OUTPUT = "text"
STRUCTURED_OUTPUT_PARAMETERS = {"structured_outputs", "response_format"}


def _capabilities(supported_parameters: list, text_output: bool = True) -> set:
    capabilities = set()
    if not text_output:
        return capabilities
    supported = set(supported_parameters or [])
    if supported & STRUCTURED_OUTPUT_PARAMETERS:
        capabilities.add(AIModelCapability.STRUCTURED_OUTPUT)
    if "temperature" in supported:
        capabilities.add(AIModelCapability.TEMPERATURE)
    if "reasoning" in supported:
        capabilities.add(AIModelCapability.REASONING)
    return capabilities


class OpenRouterClient(HttpAIClient):
    PROVIDER_NAME = "OpenRouter"
    BASE_URL = "https://openrouter.ai/api/v1"
    RETRYABLE_STATUSES = (429, 502, 503, 524, 529)

    def features(self) -> set[AIClientFeature]:
        return {
            AIClientFeature.GENERATION,
            AIClientFeature.DECISIONS,
            AIClientFeature.UPSTREAM_PROVIDERS,
            AIClientFeature.CUSTOM_MODELS,
        }

    def _headers(self, credentials: Optional[ExternalIntegrationPayload]) -> dict:
        return {"X-Title": APP_TITLE, **super()._headers(credentials)}

    async def setup(self, payload: ExternalIntegrationPayload):
        response = await self._request("GET", "/key", payload)
        if response.status in (401, 403):
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)
        if response.status == 429:
            raise TooManyRequests()
        if not response.ok:
            self._log.error(f"Error validating OpenRouter API key: {response.status}")
            response.raise_for_status()
        data = (await response.json()).get("data") or {}
        if data.get("is_management_key") or data.get("is_provisioning_key"):
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)

    async def get_model(
        self, model_id: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[AIModel]:
        path = self._model_path(model_id)
        if path is None:
            return None
        data = await self._get_data(f"/model/{path}", credentials)
        if data is None:
            return None
        output_modalities = (data.get("architecture") or {}).get(
            "output_modalities"
        ) or []
        capabilities = _capabilities(
            data.get("supported_parameters"), TEXT_OUTPUT in output_modalities
        )
        if DECISIONS_OUTPUT in output_modalities:
            capabilities.add(AIModelCapability.DECISIONS)
        return AIModel(
            id=model_id, name=data.get("name") or model_id, capabilities=capabilities
        )

    async def get_model_providers(
        self, model_id: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[list[AIModelProvider]]:
        path = self._model_path(model_id)
        if path is None:
            return None
        data = await self._get_data(f"/models/{path}/endpoints", credentials)
        if data is None:
            return None
        return [
            AIModelProvider(
                id=str(endpoint.get("tag")),
                capabilities=_capabilities(endpoint.get("supported_parameters")),
            )
            for endpoint in data.get("endpoints") or []
            if endpoint.get("tag")
        ]

    async def generate(
        self, request: AIGenerationRequest, credentials: ExternalIntegrationPayload
    ) -> AIGeneration:
        body = {"model": request.model, "messages": chat_messages(request)}
        if request.response_schema is not None:
            body["response_format"] = json_schema_format(request.response_schema)
        if request.temperature is not None:
            body["temperature"] = float(request.temperature)
        if request.reasoning_effort is not None:
            body["reasoning"] = {"effort": REASONING_EFFORTS[request.reasoning_effort]}
        if request.max_output_tokens is not None:
            body["max_tokens"] = request.max_output_tokens
        if request.upstream_provider:
            body["provider"] = {
                "order": [request.upstream_provider],
                "allow_fallbacks": False,
            }

        response = await self._send("POST", "/chat/completions", credentials, json=body)
        return parse_chat_completion(response)

    async def decide(
        self, request: AIDecisionRequest, credentials: ExternalIntegrationPayload
    ) -> AIDecisionResult:
        response = await self._send(
            "POST", "/systemone", credentials, json=decision_body(request)
        )
        return parse_decisions(response)

    async def _provider_error(self, response: HttpResponse) -> Optional[Exception]:
        if response.status == 402:
            return AIProviderError(
                AIProviderErrorCode.INSUFFICIENT_FUNDS,
                "Insufficient OpenRouter credits",
            )
        return None

    @staticmethod
    def _model_path(model_id: str) -> Optional[str]:
        if "/" not in model_id:
            return None
        author, slug = model_id.split("/", 1)
        return f"{quote(author, safe='~')}/{quote(slug, safe='~:.-_')}"

    async def _get_data(
        self, path: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[dict]:
        response = await self._request("GET", path, credentials)
        if response.status == 404:
            return None
        await self._check(response)
        data = await response.json()
        return data.get("data")
