import asyncio
import time
from typing import Callable, Optional

from application.ports.ai_client import AIClient
from application.ports.local_model_catalog import LocalModelCatalog
from application.ports.local_model_router import LocalModelRouter
from application.ports.local_model_runtime import LocalModelRuntime
from domain.ai import (
    AIClientFeature,
    AIDecisionRequest,
    AIDecisionResult,
    AIGeneration,
    AIGenerationRequest,
    AIModel,
    AIModelCapability,
)
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    LocalModelError,
    LocalModelErrorCode,
)
from domain.external_integration import ExternalIntegrationPayload
from domain.local_model import (
    IMPORTED_MODEL_PREFIX,
    USABLE_LOCAL_MODEL_STATES,
    LocalModelCatalogEntry,
    LocalModelState,
    LocalRouterConnection,
    LocalRouterModel,
    is_imported_model_id,
)
from infrastructure.client.ai.openai_compatible.openai_compatible_client import (
    OpenAICompatibleClient,
)

SETUP_ERROR_CODES = {
    LocalModelErrorCode.MISSING_SERVER_URL: IntegrationSetupErrorCode.MISSING_SERVER_URL,
    LocalModelErrorCode.INVALID_URL: IntegrationSetupErrorCode.INVALID_URL,
    LocalModelErrorCode.UNAUTHORIZED: IntegrationSetupErrorCode.INVALID_CREDENTIALS,
    LocalModelErrorCode.NOT_A_MODEL_ROUTER: IntegrationSetupErrorCode.NOT_A_MODEL_ROUTER,
}
API_PATH = "/v1"


class LlamaInferenceClient(OpenAICompatibleClient):
    PROVIDER_NAME = "llama.cpp server"


def model_capabilities(
    model: LocalRouterModel, entry: Optional[LocalModelCatalogEntry] = None
) -> set[AIModelCapability]:
    if model.decisions or (entry is not None and entry.decisions):
        return {AIModelCapability.DECISIONS}
    return {AIModelCapability.STRUCTURED_OUTPUT, AIModelCapability.TEMPERATURE}


class LocalModelsAIClient(AIClient):
    LOAD_TIMEOUT_SECONDS = 180.0
    LOAD_POLL_SECONDS = 1.0

    def __init__(
        self,
        runtime: LocalModelRuntime,
        router: LocalModelRouter,
        catalog: LocalModelCatalog,
        inference: Optional[OpenAICompatibleClient] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._runtime = runtime
        self._router = router
        self._catalog = catalog
        self._inference = inference or LlamaInferenceClient()
        self._clock = clock

    def features(self) -> set[AIClientFeature]:
        return {
            AIClientFeature.GENERATION,
            AIClientFeature.DECISIONS,
            AIClientFeature.MODEL_LISTING,
        }

    async def setup(self, payload: ExternalIntegrationPayload):
        try:
            connection = await self._runtime.resolve(payload)
            await self._router.probe(connection)
        except LocalModelError as e:
            raise IntegrationSetupError(
                SETUP_ERROR_CODES.get(e.code, IntegrationSetupErrorCode.UNREACHABLE)
            ) from e

    async def teardown(self):
        await self._runtime.stop()

    async def list_models(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> list[AIModel]:
        connection = await self._connection(credentials)
        models = [
            self._to_ai_model(model)
            for model in await self._models(connection)
            if model.state in USABLE_LOCAL_MODEL_STATES
        ]
        return sorted(models, key=lambda model: model.name.casefold())

    def _to_ai_model(self, model: LocalRouterModel) -> AIModel:
        entry = self._catalog.find(model.id)
        if entry is not None:
            name = entry.name
        elif is_imported_model_id(model.id):
            name = model.id[len(IMPORTED_MODEL_PREFIX) :]
        else:
            name = model.id
        return AIModel(
            id=model.id,
            name=name,
            capabilities=model_capabilities(model, entry),
            size=model.size or (entry.size if entry else None),
            loaded=model.state == LocalModelState.LOADED,
            load_failed=model.state == LocalModelState.FAILED,
        )

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
        connection = await self._ready(request.model, credentials)
        return await self._inference.generate(
            request, self._inference_credentials(connection)
        )

    async def decide(
        self, request: AIDecisionRequest, credentials: ExternalIntegrationPayload
    ) -> AIDecisionResult:
        connection = await self._ready(request.model, credentials)
        return await self._inference.decide(
            request, self._inference_credentials(connection)
        )

    async def _ready(
        self, model_id: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> LocalRouterConnection:
        connection = await self._connection(credentials)
        model = self._find(await self._models(connection), model_id)
        if model is None or model.state not in USABLE_LOCAL_MODEL_STATES:
            raise AIProviderError(
                AIProviderErrorCode.MODEL_NOT_FOUND, f"Model {model_id} not available"
            )
        if model.state in (LocalModelState.LOADED, LocalModelState.SLEEPING):
            return connection

        if model.state in (LocalModelState.UNLOADED, LocalModelState.FAILED):
            await self._call(self._router.load(connection, model_id))

        deadline = self._clock() + self.LOAD_TIMEOUT_SECONDS
        while self._clock() < deadline:
            await asyncio.sleep(self.LOAD_POLL_SECONDS)
            model = self._find(await self._models(connection), model_id)
            if model is None:
                raise AIProviderError(
                    AIProviderErrorCode.MODEL_NOT_FOUND,
                    f"Model {model_id} not available",
                )
            if model.state in (LocalModelState.LOADED, LocalModelState.SLEEPING):
                return connection
            if model.state == LocalModelState.FAILED:
                raise AIProviderError(
                    AIProviderErrorCode.UNAVAILABLE,
                    f"Model {model_id} failed to load",
                )
        raise AIProviderError(
            AIProviderErrorCode.UNAVAILABLE, f"Model {model_id} took too long to load"
        )

    async def _connection(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> LocalRouterConnection:
        return await self._call(self._runtime.resolve(credentials))

    async def _models(
        self, connection: LocalRouterConnection
    ) -> list[LocalRouterModel]:
        return await self._call(self._router.list_models(connection))

    @staticmethod
    def _find(
        models: list[LocalRouterModel], model_id: str
    ) -> Optional[LocalRouterModel]:
        return next((model for model in models if model.id == model_id), None)

    @staticmethod
    async def _call(awaitable):
        try:
            return await awaitable
        except LocalModelError as e:
            raise AIProviderError(AIProviderErrorCode.UNAVAILABLE, e.details) from e

    @staticmethod
    def _inference_credentials(
        connection: LocalRouterConnection,
    ) -> ExternalIntegrationPayload:
        credentials = {"base_url": f"{connection.base_url}{API_PATH}"}
        if connection.api_key:
            credentials["api_key"] = connection.api_key
        return credentials
