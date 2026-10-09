from typing import Optional
from urllib.parse import quote

from domain.ai import (
    AIClientFeature,
    AIGeneration,
    AIGenerationRequest,
    AIGenerationStatus,
    AIModel,
    AIModelCapability,
    AIUsage,
)
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

INSUFFICIENT_QUOTA = "insufficient_quota"

NON_TEXT_MODEL_PREFIXES = (
    "text-embedding",
    "tts",
    "whisper",
    "dall-e",
    "gpt-image",
    "chatgpt-image",
    "omni-moderation",
    "text-moderation",
    "sora",
    "babbage",
    "davinci",
    "computer-use",
)
NON_TEXT_MODEL_MARKERS = ("-realtime", "-transcribe", "-tts", "-audio", "-search-api")


def _is_text_model(model_id: str) -> bool:
    normalized = model_id.casefold()
    return not normalized.startswith(NON_TEXT_MODEL_PREFIXES) and not any(
        marker in normalized for marker in NON_TEXT_MODEL_MARKERS
    )


class OpenAIClient(HttpAIClient):
    PROVIDER_NAME = "OpenAI"
    BASE_URL = "https://api.openai.com/v1"

    def features(self) -> set[AIClientFeature]:
        return {AIClientFeature.GENERATION}

    async def setup(self, payload: ExternalIntegrationPayload):
        response = await self._request("GET", "/models", payload)
        if response.status in (401, 403):
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)
        if response.status == 429:
            raise TooManyRequests()
        if not response.ok:
            self._log.error(f"Error validating OpenAI API key: {response.status}")
            response.raise_for_status()

    async def get_model(
        self, model_id: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[AIModel]:
        response = await self._request(
            "GET", f"/models/{quote(model_id, safe='')}", credentials
        )
        if response.status == 404:
            return None
        await self._check(response)
        data = await response.json()
        capabilities = (
            {AIModelCapability.STRUCTURED_OUTPUT} if _is_text_model(model_id) else set()
        )
        return AIModel(
            id=data.get("id") or model_id, name=model_id, capabilities=capabilities
        )

    async def generate(
        self, request: AIGenerationRequest, credentials: ExternalIntegrationPayload
    ) -> AIGeneration:
        if request.upstream_provider:
            raise AIProviderError(
                AIProviderErrorCode.UNSUPPORTED_OPERATION,
                "OpenAI does not support upstream providers",
            )
        body = {
            "model": request.model,
            "input": [
                {"role": message.role.value.lower(), "content": message.content}
                for message in request.messages
            ],
            "store": False,
        }
        if request.instructions:
            body["instructions"] = request.instructions
        if request.response_schema is not None:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": request.response_schema.name,
                    "strict": True,
                    "schema": request.response_schema.schema,
                }
            }
        if request.temperature is not None:
            body["temperature"] = float(request.temperature)
        if request.reasoning_effort is not None:
            body["reasoning"] = {"effort": REASONING_EFFORTS[request.reasoning_effort]}
        if request.max_output_tokens is not None:
            body["max_output_tokens"] = request.max_output_tokens

        response = await self._send("POST", "/responses", credentials, json=body)

        texts, refusals = [], []
        for item in response.get("output") or []:
            if item.get("type") != "message":
                continue
            for part in item.get("content") or []:
                if part.get("type") == "output_text":
                    texts.append(part.get("text") or "")
                elif part.get("type") == "refusal":
                    refusals.append(part.get("refusal") or "")

        if refusals:
            generation_status = AIGenerationStatus.REFUSED
        elif response.get("status") == "incomplete":
            generation_status = AIGenerationStatus.INCOMPLETE
        else:
            generation_status = AIGenerationStatus.COMPLETED
        usage = response.get("usage") or {}
        return AIGeneration(
            status=generation_status,
            text="".join(texts) or None,
            refusal="".join(refusals) or None,
            usage=AIUsage(
                input_tokens=usage.get("input_tokens") or 0,
                output_tokens=usage.get("output_tokens") or 0,
            )
            if usage
            else None,
        )

    async def _should_retry(self, response: HttpResponse) -> bool:
        if response.status == 429 and await self._is_quota_error(response):
            return False
        return await super()._should_retry(response)

    async def _provider_error(self, response: HttpResponse) -> Optional[Exception]:
        if response.status == 429 and await self._is_quota_error(response):
            return AIProviderError(
                AIProviderErrorCode.INSUFFICIENT_FUNDS, "Insufficient OpenAI quota"
            )
        return None

    async def _is_quota_error(self, response: HttpResponse) -> bool:
        error = await self._error_body(response)
        return INSUFFICIENT_QUOTA in (error.get("code"), error.get("type"))
