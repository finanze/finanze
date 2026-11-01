import pytest
from application.ports.local_model_catalog import LocalModelCatalog
from domain.ai import (
    AIChoiceQuestion,
    AIClientFeature,
    AIDecisionRequest,
    AIDecisionResult,
    AIGeneration,
    AIGenerationRequest,
    AIGenerationStatus,
    AIMessage,
    AIMessageRole,
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
from domain.local_model import (
    LocalModelCatalogEntry,
    LocalModelState,
    LocalRouterConnection,
    LocalRouterModel,
    LocalRuntimeMode,
    LocalRuntimeSource,
)
from infrastructure.local_models.local_models_ai_client import LocalModelsAIClient

CONNECTION = LocalRouterConnection(
    base_url="http://127.0.0.1:5000",
    api_key="generated",
    mode=LocalRuntimeMode.BUILT_IN,
    source=LocalRuntimeSource.BUILT_IN,
)
CATALOG_ID = "ggml-org/Laya-GGUF:Q8_0"
ENTRY = LocalModelCatalogEntry(
    id=CATALOG_ID,
    name="Laya",
    repo="ggml-org/Laya-GGUF",
    quant="Q8_0",
    size=1000,
    ram=2000,
    params="0.4B",
    license="apache-2.0",
    decisions=True,
)


class FakeCatalog(LocalModelCatalog):
    def entries(self):
        return [ENTRY]


class FakeRuntime:
    def __init__(self, connection=CONNECTION, error=None):
        self.connection = connection
        self.error = error
        self.stopped = 0
        self.resolved = []

    async def resolve(self, credentials):
        self.resolved.append(credentials)
        if self.error:
            raise self.error
        return self.connection

    async def stop(self):
        self.stopped += 1


class FakeRouter:
    def __init__(self, *snapshots: list[LocalRouterModel], probe_error=None):
        self.snapshots = list(snapshots)
        self.probe_error = probe_error
        self.loaded: list[str] = []
        self.probed = 0

    async def probe(self, connection):
        self.probed += 1
        if self.probe_error:
            raise self.probe_error

    async def list_models(self, connection, reload=False):
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]

    async def load(self, connection, model_id):
        self.loaded.append(model_id)


class FakeInference:
    def __init__(self):
        self.generate_calls = []
        self.decide_calls = []

    async def generate(self, request, credentials):
        self.generate_calls.append((request, credentials))
        return AIGeneration(status=AIGenerationStatus.COMPLETED, text="{}")

    async def decide(self, request, credentials):
        self.decide_calls.append((request, credentials))
        return AIDecisionResult(answers={})


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def _model(model_id: str, state=LocalModelState.UNLOADED, **kwargs):
    return LocalRouterModel(id=model_id, state=state, **kwargs)


def _client(router, runtime=None, inference=None, clock=None) -> LocalModelsAIClient:
    client = LocalModelsAIClient(
        runtime or FakeRuntime(),
        router,
        FakeCatalog(),
        inference=inference or FakeInference(),
        clock=clock or Clock(),
    )
    client.LOAD_POLL_SECONDS = 0
    return client


def _request(model: str) -> AIGenerationRequest:
    return AIGenerationRequest(
        model=model, messages=[AIMessage(role=AIMessageRole.USER, content="hi")]
    )


def test_features():
    assert _client(FakeRouter([])).features() == {
        AIClientFeature.GENERATION,
        AIClientFeature.DECISIONS,
        AIClientFeature.MODEL_LISTING,
    }


class TestSetup:
    @pytest.mark.asyncio
    async def test_probes_router(self):
        router = FakeRouter([])
        runtime = FakeRuntime()
        await _client(router, runtime).setup({})
        assert runtime.resolved == [{}]
        assert router.probed == 1

    @pytest.mark.parametrize(
        "code, expected",
        [
            (
                LocalModelErrorCode.MISSING_SERVER_URL,
                IntegrationSetupErrorCode.MISSING_SERVER_URL,
            ),
            (LocalModelErrorCode.INVALID_URL, IntegrationSetupErrorCode.INVALID_URL),
            (
                LocalModelErrorCode.UNAUTHORIZED,
                IntegrationSetupErrorCode.INVALID_CREDENTIALS,
            ),
            (
                LocalModelErrorCode.NOT_A_MODEL_ROUTER,
                IntegrationSetupErrorCode.NOT_A_MODEL_ROUTER,
            ),
            (LocalModelErrorCode.UNREACHABLE, IntegrationSetupErrorCode.UNREACHABLE),
            (LocalModelErrorCode.RUNTIME_FAILED, IntegrationSetupErrorCode.UNREACHABLE),
        ],
    )
    @pytest.mark.asyncio
    async def test_maps_errors(self, code, expected):
        router = FakeRouter([], probe_error=LocalModelError(code))
        with pytest.raises(IntegrationSetupError) as error:
            await _client(router).setup({"server_url": "http://x"})
        assert error.value.code == expected

    @pytest.mark.asyncio
    async def test_runtime_error(self):
        runtime = FakeRuntime(
            error=LocalModelError(LocalModelErrorCode.MISSING_SERVER_URL)
        )
        with pytest.raises(IntegrationSetupError) as error:
            await _client(FakeRouter([]), runtime).setup({})
        assert error.value.code == IntegrationSetupErrorCode.MISSING_SERVER_URL

    @pytest.mark.asyncio
    async def test_teardown_stops_runtime(self):
        runtime = FakeRuntime()
        await _client(FakeRouter([]), runtime).teardown()
        assert runtime.stopped == 1


class TestListModels:
    @pytest.mark.asyncio
    async def test_lists_usable_models(self):
        router = FakeRouter(
            [
                _model("zeta:Q4", LocalModelState.LOADED, size=50),
                _model(CATALOG_ID),
                _model("local/my-model", LocalModelState.SLEEPING),
                _model("org/new-GGUF:Q4", LocalModelState.DOWNLOADING),
                _model("custom", LocalModelState.FAILED, decisions=True),
            ]
        )
        models = await _client(router).list_models({})
        assert [(m.id, m.name) for m in models] == [
            ("custom", "custom"),
            (CATALOG_ID, "Laya"),
            ("local/my-model", "my-model"),
            ("zeta:Q4", "zeta:Q4"),
        ]
        by_id = {m.id: m for m in models}
        assert by_id[CATALOG_ID].capabilities == {AIModelCapability.DECISIONS}
        assert by_id[CATALOG_ID].size == 1000
        assert by_id["custom"].capabilities == {AIModelCapability.DECISIONS}
        assert by_id["zeta:Q4"].capabilities == {
            AIModelCapability.STRUCTURED_OUTPUT,
            AIModelCapability.TEMPERATURE,
        }
        assert by_id["zeta:Q4"].loaded is True
        assert by_id["zeta:Q4"].size == 50
        assert by_id["local/my-model"].loaded is False
        assert by_id["custom"].load_failed is True
        assert by_id["zeta:Q4"].load_failed is False

    @pytest.mark.asyncio
    async def test_runtime_errors_are_provider_errors(self):
        runtime = FakeRuntime(error=LocalModelError(LocalModelErrorCode.UNREACHABLE))
        with pytest.raises(AIProviderError) as error:
            await _client(FakeRouter([]), runtime).list_models({})
        assert error.value.code == AIProviderErrorCode.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_get_model(self):
        client = _client(FakeRouter([_model("a:Q4")]))
        assert (await client.get_model("a:Q4", {})).id == "a:Q4"
        assert await client.get_model("b:Q4", {}) is None


class TestReadiness:
    @pytest.mark.parametrize(
        "state", [LocalModelState.LOADED, LocalModelState.SLEEPING]
    )
    @pytest.mark.asyncio
    async def test_ready_model_is_used_directly(self, state):
        router = FakeRouter([_model("a:Q4", state)])
        inference = FakeInference()
        await _client(router, inference=inference).generate(_request("a:Q4"), {})
        assert router.loaded == []
        request, credentials = inference.generate_calls[0]
        assert request.model == "a:Q4"
        assert credentials == {
            "base_url": "http://127.0.0.1:5000/v1",
            "api_key": "generated",
        }

    @pytest.mark.asyncio
    async def test_loads_and_waits(self):
        router = FakeRouter(
            [_model("a:Q4")],
            [_model("a:Q4", LocalModelState.LOADING)],
            [_model("a:Q4", LocalModelState.LOADED)],
        )
        inference = FakeInference()
        await _client(router, inference=inference).generate(_request("a:Q4"), {})
        assert router.loaded == ["a:Q4"]
        assert len(inference.generate_calls) == 1

    @pytest.mark.asyncio
    async def test_retries_failed_model(self):
        router = FakeRouter(
            [_model("a:Q4", LocalModelState.FAILED)],
            [_model("a:Q4", LocalModelState.LOADED)],
        )
        await _client(router).generate(_request("a:Q4"), {})
        assert router.loaded == ["a:Q4"]

    @pytest.mark.asyncio
    async def test_waits_for_loading_model_without_reloading(self):
        router = FakeRouter(
            [_model("a:Q4", LocalModelState.LOADING)],
            [_model("a:Q4", LocalModelState.LOADED)],
        )
        await _client(router).generate(_request("a:Q4"), {})
        assert router.loaded == []

    @pytest.mark.parametrize(
        "snapshot", [[], [_model("a:Q4", LocalModelState.DOWNLOADING)]]
    )
    @pytest.mark.asyncio
    async def test_unavailable_model(self, snapshot):
        with pytest.raises(AIProviderError) as error:
            await _client(FakeRouter(snapshot)).generate(_request("a:Q4"), {})
        assert error.value.code == AIProviderErrorCode.MODEL_NOT_FOUND

    @pytest.mark.asyncio
    async def test_load_failure(self):
        router = FakeRouter(
            [_model("a:Q4")],
            [_model("a:Q4", LocalModelState.FAILED)],
        )
        with pytest.raises(AIProviderError) as error:
            await _client(router).generate(_request("a:Q4"), {})
        assert error.value.code == AIProviderErrorCode.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_model_removed_while_loading(self):
        router = FakeRouter([_model("a:Q4")], [])
        with pytest.raises(AIProviderError) as error:
            await _client(router).generate(_request("a:Q4"), {})
        assert error.value.code == AIProviderErrorCode.MODEL_NOT_FOUND

    @pytest.mark.asyncio
    async def test_load_timeout(self):
        clock = Clock()

        class SlowRouter(FakeRouter):
            async def list_models(self, connection, reload=False):
                clock.now += 100
                return [_model("a:Q4", LocalModelState.LOADING)]

        with pytest.raises(AIProviderError) as error:
            await _client(SlowRouter(), clock=clock).generate(_request("a:Q4"), {})
        assert error.value.code == AIProviderErrorCode.UNAVAILABLE
        assert "too long" in error.value.details

    @pytest.mark.asyncio
    async def test_decide_without_api_key(self):
        open_connection = LocalRouterConnection(
            base_url="http://server:8080",
            mode=LocalRuntimeMode.EXTERNAL,
            source=LocalRuntimeSource.PAYLOAD,
        )
        inference = FakeInference()
        client = _client(
            FakeRouter([_model(CATALOG_ID, LocalModelState.LOADED)]),
            FakeRuntime(open_connection),
            inference,
        )
        await client.decide(
            AIDecisionRequest(
                model=CATALOG_ID,
                state={},
                questions=[AIChoiceQuestion(id="m1", instructions="x", options=["a"])],
            ),
            {"server_url": "http://server:8080"},
        )
        assert inference.decide_calls[0][1] == {"base_url": "http://server:8080/v1"}
