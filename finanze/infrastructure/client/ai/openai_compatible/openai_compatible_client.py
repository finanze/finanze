import json
import time
from typing import Optional

from domain.ai import (
    AIClientFeature,
    AIDecisionRequest,
    AIDecisionResult,
    AIGeneration,
    AIGenerationRequest,
    AIModel,
    AIModelCapability,
    AIServerError,
    AIServerInfo,
)
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import ExternalIntegrationPayload
from infrastructure.client.ai.chat_completions import (
    chat_messages,
    decision_body,
    json_schema_format,
    parse_chat_completion,
    parse_decisions,
)
from infrastructure.client.ai.http_ai_client import REASONING_EFFORTS, HttpAIClient
from infrastructure.client.ai.openai_compatible.server_details import (
    describe_server,
    detect_server_kind,
    parse_server_model,
)
from infrastructure.client.ai.server_url import (
    TRANSPORT_ERRORS,
    api_base_url,
    server_root_url,
    unreachable,
)
from infrastructure.client.http.http_response import HttpResponse

DECISIONS_OUTPUT = "decisions"
TEXT_OUTPUT = "text"
JSON_SCHEMA_UNSUPPORTED_STATUSES = (400, 422)
JSON_OBJECT_INSTRUCTIONS = (
    "Reply only with a JSON object that matches this JSON schema:\n{schema}"
)


def model_capabilities(entry: dict) -> set[AIModelCapability]:
    modalities = (entry.get("architecture") or {}).get("output_modalities")
    capabilities = set()
    if not isinstance(modalities, list) or TEXT_OUTPUT in modalities:
        capabilities |= {
            AIModelCapability.STRUCTURED_OUTPUT,
            AIModelCapability.TEMPERATURE,
        }
    if isinstance(modalities, list) and DECISIONS_OUTPUT in modalities:
        capabilities.add(AIModelCapability.DECISIONS)
    return capabilities


class OpenAICompatibleClient(HttpAIClient):
    PROVIDER_NAME = "Custom AI"
    REQUEST_TIMEOUT_SECONDS = 300.0
    SETUP_TIMEOUT_SECONDS = 15.0
    PROBE_TIMEOUT_SECONDS = 5.0
    MAX_RETRIES = 2
    RETRYABLE_STATUSES = (429, 502, 503)

    def __init__(self):
        super().__init__()
        self._json_object_models: set[tuple[str, str]] = set()

    def features(self) -> set[AIClientFeature]:
        return {
            AIClientFeature.GENERATION,
            AIClientFeature.DECISIONS,
            AIClientFeature.MODEL_LISTING,
            AIClientFeature.CUSTOM_MODELS,
            AIClientFeature.SERVER_INFO,
        }

    def _base_url(self, credentials: Optional[ExternalIntegrationPayload]) -> str:
        try:
            return api_base_url((credentials or {}).get("base_url"))
        except ValueError:
            raise AIProviderError(
                AIProviderErrorCode.UNAVAILABLE,
                f"Invalid {self.PROVIDER_NAME} URL",
            )

    async def _request(
        self,
        method: str,
        path: str,
        credentials: Optional[ExternalIntegrationPayload],
        **kwargs,
    ) -> HttpResponse:
        try:
            return await super()._request(method, path, credentials, **kwargs)
        except TRANSPORT_ERRORS as e:
            raise unreachable(self.PROVIDER_NAME, e) from e

    async def setup(self, payload: ExternalIntegrationPayload):
        try:
            api_base_url(payload.get("base_url"))
        except ValueError:
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_URL)
        try:
            response = await self._request(
                "GET", "/models", payload, timeout=self.SETUP_TIMEOUT_SECONDS
            )
        except AIProviderError:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNREACHABLE)
        if response.status in (401, 403):
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)
        if response.status in (404, 405):
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_URL)
        if not response.ok:
            self._log.warning(
                f"{self.PROVIDER_NAME} model listing failed with status {response.status}"
            )
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNREACHABLE)
        try:
            body = await response.json()
        except ValueError:
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_URL)
        if not isinstance(body, dict) or not isinstance(body.get("data"), list):
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_URL)

    async def list_models(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> list[AIModel]:
        body = await self._send("GET", "/models", credentials)
        models = [
            AIModel(
                id=str(entry["id"]),
                name=str(entry.get("name") or entry["id"]),
                capabilities=model_capabilities(entry),
            )
            for entry in body.get("data") or []
            if isinstance(entry, dict) and entry.get("id")
        ]
        return sorted(models, key=lambda model: model.name.casefold())

    async def get_server_info(
        self, credentials: ExternalIntegrationPayload
    ) -> AIServerInfo:
        base_url = self._base_url(credentials)
        info = AIServerInfo(url=base_url, api_key_set=bool(self._api_key(credentials)))
        started = time.perf_counter()
        try:
            response = await self._session.request(
                "GET",
                f"{base_url}/models",
                headers=self._headers(credentials),
                timeout=self.SETUP_TIMEOUT_SECONDS,
            )
        except TRANSPORT_ERRORS:
            info.error = AIServerError.UNREACHABLE
            return info
        info.reachable = True
        info.latency_ms = round((time.perf_counter() - started) * 1000)
        if response.status in (401, 403):
            info.error = AIServerError.UNAUTHORIZED
        elif response.status in (404, 405):
            info.error = AIServerError.NOT_FOUND
        elif not response.ok:
            info.error = AIServerError.SERVER_ERROR
        if info.error is not None:
            return info
        try:
            body = await response.json()
        except ValueError:
            body = None
        entries = body.get("data") if isinstance(body, dict) else None
        if not isinstance(entries, list):
            info.error = AIServerError.INVALID_RESPONSE
            return info
        entries = [
            entry for entry in entries if isinstance(entry, dict) and entry.get("id")
        ]
        info.models = [
            parse_server_model(
                entry, AIModelCapability.DECISIONS in model_capabilities(entry)
            )
            for entry in entries
        ]
        root = server_root_url(base_url)
        info.kind, info.version = await describe_server(
            detect_server_kind(entries),
            info.models,
            lambda path: self._probe(f"{root}{path}", credentials),
        )
        info.models.sort(key=lambda model: model.id.casefold())
        return info

    async def _probe(
        self, url: str, credentials: ExternalIntegrationPayload
    ) -> Optional[dict]:
        try:
            response = await self._session.request(
                "GET",
                url,
                headers=self._headers(credentials),
                timeout=self.PROBE_TIMEOUT_SECONDS,
            )
            if not response.ok:
                return None
            body = await response.json()
        except (*TRANSPORT_ERRORS, ValueError):
            return None
        return body if isinstance(body, dict) else None

    async def get_model(
        self, model_id: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[AIModel]:
        return next(
            (
                model
                for model in await self.list_models(credentials)
                if model.id == model_id
            ),
            None,
        )

    async def generate(
        self, request: AIGenerationRequest, credentials: ExternalIntegrationPayload
    ) -> AIGeneration:
        key = (self._base_url(credentials), request.model)
        if request.response_schema is None or key in self._json_object_models:
            return await self._complete(request, credentials, json_schema=False)

        response = await self._request(
            "POST",
            "/chat/completions",
            credentials,
            json=self._body(request, json_schema=True),
        )
        if response.status not in JSON_SCHEMA_UNSUPPORTED_STATUSES:
            await self._check(response)
            return parse_chat_completion(await response.json())

        self._log.info(
            f"{self.PROVIDER_NAME} rejected json_schema for {request.model}, retrying with json_object"
        )
        generation = await self._complete(request, credentials, json_schema=False)
        self._json_object_models.add(key)
        return generation

    async def decide(
        self, request: AIDecisionRequest, credentials: ExternalIntegrationPayload
    ) -> AIDecisionResult:
        response = await self._send(
            "POST", "/systemone", credentials, json=decision_body(request)
        )
        return parse_decisions(response)

    async def _complete(
        self,
        request: AIGenerationRequest,
        credentials: ExternalIntegrationPayload,
        json_schema: bool,
    ) -> AIGeneration:
        response = await self._send(
            "POST",
            "/chat/completions",
            credentials,
            json=self._body(request, json_schema=json_schema),
        )
        return parse_chat_completion(response)

    @staticmethod
    def _body(request: AIGenerationRequest, json_schema: bool) -> dict:
        messages = chat_messages(request)
        body = {"model": request.model, "messages": messages}
        if request.response_schema is not None:
            if json_schema:
                body["response_format"] = json_schema_format(request.response_schema)
            else:
                body["response_format"] = {"type": "json_object"}
                schema_instructions = JSON_OBJECT_INSTRUCTIONS.format(
                    schema=json.dumps(request.response_schema.schema)
                )
                if messages and messages[0]["role"] == "system":
                    messages[0]["content"] += "\n\n" + schema_instructions
                else:
                    messages.insert(
                        0, {"role": "system", "content": schema_instructions}
                    )
        if request.temperature is not None:
            body["temperature"] = float(request.temperature)
        if request.reasoning_effort is not None:
            body["reasoning_effort"] = REASONING_EFFORTS[request.reasoning_effort]
        if request.max_output_tokens is not None:
            body["max_tokens"] = request.max_output_tokens
        return body
