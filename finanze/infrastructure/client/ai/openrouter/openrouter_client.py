from typing import Optional
from urllib.parse import quote

from domain.ai import (
    AIClientFeature,
    AIDecisionAnswer,
    AIDecisionRequest,
    AIDecisionResult,
    AIGeneration,
    AIGenerationRequest,
    AIGenerationStatus,
    AIModel,
    AIModelCapability,
    AIModelProvider,
    AIUsage,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    TooManyRequests,
)
from domain.external_integration import ExternalIntegrationPayload
from infrastructure.client.ai.http_ai_client import REASONING_EFFORTS, HttpAIClient
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


def _to_dezimal(value) -> Optional[Dezimal]:
    if value is None:
        return None
    try:
        return Dezimal(str(value))
    except ValueError:
        return None


class OpenRouterClient(HttpAIClient):
    PROVIDER_NAME = "OpenRouter"
    BASE_URL = "https://openrouter.ai/api/v1"
    RETRYABLE_STATUSES = (429, 502, 503, 524, 529)

    def features(self) -> set[AIClientFeature]:
        return {
            AIClientFeature.GENERATION,
            AIClientFeature.DECISIONS,
            AIClientFeature.UPSTREAM_PROVIDERS,
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
        messages = []
        if request.instructions:
            messages.append({"role": "system", "content": request.instructions})
        messages += [
            {"role": message.role.value.lower(), "content": message.content}
            for message in request.messages
        ]
        body = {"model": request.model, "messages": messages}
        if request.response_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.response_schema.name,
                    "strict": True,
                    "schema": request.response_schema.schema,
                },
            }
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

        choices = response.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        usage = response.get("usage") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if message.get("refusal"):
            generation_status = AIGenerationStatus.REFUSED
        elif choice.get("finish_reason") == "length":
            generation_status = AIGenerationStatus.INCOMPLETE
        else:
            generation_status = AIGenerationStatus.COMPLETED
        return AIGeneration(
            status=generation_status,
            text=content or None,
            refusal=message.get("refusal"),
            usage=AIUsage(
                input_tokens=usage.get("prompt_tokens") or 0,
                output_tokens=usage.get("completion_tokens") or 0,
            )
            if usage
            else None,
        )

    async def decide(
        self, request: AIDecisionRequest, credentials: ExternalIntegrationPayload
    ) -> AIDecisionResult:
        body = {
            "model": request.model,
            "state": request.state,
            "questions": {
                question.id: {
                    "type": "choice",
                    "instructions": question.instructions,
                    "criteria": dict.fromkeys(question.options),
                }
                for question in request.questions
            },
        }
        response = await self._send("POST", "/systemone", credentials, json=body)

        answers = {}
        for question_id, answer in (response.get("answers") or {}).items():
            if not isinstance(answer, dict):
                continue
            probabilities = {
                option: probability
                for option, value in (answer.get("probabilities") or {}).items()
                if (probability := _to_dezimal(value)) is not None
            }
            answers[question_id] = AIDecisionAnswer(
                choice=answer.get("choice"),
                confidence=_to_dezimal(answer.get("confidence")),
                probabilities=probabilities,
            )
        return AIDecisionResult(answers=answers)

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
