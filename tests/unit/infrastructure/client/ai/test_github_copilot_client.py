from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from domain.ai import (
    AIClientFeature,
    AIGenerationRequest,
    AIGenerationStatus,
    AIJsonSchema,
    AIMessage,
    AIMessageRole,
    AIModelCapability,
    AIModelPricing,
    AIReasoningEffort,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from infrastructure.agent_runtime.runtime_pool import AgentRuntimePool
from infrastructure.agent_runtime.runtime_sandbox import AgentRuntimeSandbox
from infrastructure.client.ai.github_copilot.copilot_runtime_provisioner import (
    CopilotRuntimeUnavailable,
)
from infrastructure.client.ai.github_copilot.copilot_runtime_types import (
    CopilotErrorKind,
    CopilotModelEntry,
    CopilotRuntimeError,
)
from infrastructure.client.ai.github_copilot.github_copilot_client import (
    CATALOG_TTL_SECONDS,
    GENERATION_TIMEOUT_SECONDS,
    GITHUB_COPILOT_CLIENT_ID,
    GITHUB_COPILOT_CLIENT_ID_ENV,
    GitHubCopilotClient,
    resolve_github_copilot_client_id,
)

TOKEN = "gho_token"
CREDENTIALS = {"access_token": TOKEN}
EXECUTABLE = "/runtime/copilot"
SCHEMA = {"type": "object", "properties": {}}
MINI_PRICING = AIModelPricing(
    input_per_million=Dezimal("0.1"), output_per_million=Dezimal("0.5")
)
MODELS = [
    CopilotModelEntry(
        id="gpt-5-mini",
        name="GPT-5 mini",
        enabled=True,
        pricing=MINI_PRICING,
    ),
    CopilotModelEntry(
        id="claude-sonnet",
        name="Claude Sonnet",
        enabled=True,
        reasoning_efforts=("low", "medium", "high"),
    ),
    CopilotModelEntry(
        id="o-high", name="O High", enabled=True, reasoning_efforts=("high", "max")
    ),
    CopilotModelEntry(id="disabled-model", name="Disabled", enabled=False),
]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeRuntime:
    def __init__(self, env: "Env"):
        self.env = env
        self.stopped = False

    async def stop(self):
        self.stopped = True

    async def is_authenticated(self) -> bool:
        return self.env.authenticated

    async def list_models(self) -> list[CopilotModelEntry]:
        self.env.list_calls += 1
        if self.env.list_error:
            raise self.env.list_error
        return list(self.env.models)

    async def complete(self, **kwargs):
        self.env.completions.append(kwargs)
        if self.env.complete_error:
            raise self.env.complete_error
        return self.env.text


class FakeProvisioner:
    def __init__(self):
        self.prefetched = 0
        self.error: Exception | None = None

    def prefetch(self):
        self.prefetched += 1

    async def ensure(self) -> str:
        if self.error:
            raise self.error
        return EXECUTABLE


class Env:
    def __init__(self, tmp_path):
        self.authenticated = True
        self.models = MODELS
        self.list_error: Exception | None = None
        self.complete_error: Exception | None = None
        self.factory_error: Exception | None = None
        self.text = '{"labels": []}'
        self.list_calls = 0
        self.completions: list[dict] = []
        self.runtimes: list[FakeRuntime] = []
        self.started: list[tuple] = []
        self.clock = Clock()
        self.provisioner = FakeProvisioner()
        self.device_flow = AsyncMock()
        self.pool = AgentRuntimePool()
        self.sandbox = AgentRuntimeSandbox(tmp_path)
        self.tmp_path = tmp_path
        self.client = GitHubCopilotClient(
            self.device_flow,
            self.provisioner,
            self.pool,
            self.sandbox,
            runtime_factory=self.factory,
            clock=self.clock,
        )

    async def factory(self, executable, token, dirs):
        self.started.append((executable, token, dirs))
        if self.factory_error:
            raise self.factory_error
        runtime = FakeRuntime(self)
        self.runtimes.append(runtime)
        return runtime


@pytest_asyncio.fixture
async def env(tmp_path):
    environment = Env(tmp_path)
    yield environment
    await environment.pool.release_all()


def _request(model="claude-sonnet", **kwargs) -> AIGenerationRequest:
    return AIGenerationRequest(
        model=model,
        messages=[
            AIMessage(role=AIMessageRole.USER, content="first"),
            AIMessage(role=AIMessageRole.USER, content="second"),
        ],
        instructions="Label movements",
        response_schema=AIJsonSchema(name="labels", schema=SCHEMA),
        **kwargs,
    )


async def _setup_error(env, code: IntegrationSetupErrorCode, payload=None):
    with pytest.raises(IntegrationSetupError) as error:
        await env.client.setup(CREDENTIALS if payload is None else payload)
    assert error.value.code == code


async def _provider_error(call, code: AIProviderErrorCode):
    with pytest.raises(AIProviderError) as error:
        await call
    assert error.value.code == code


def test_features_and_client_id(monkeypatch, tmp_path):
    client = GitHubCopilotClient(
        AsyncMock(),
        FakeProvisioner(),
        AgentRuntimePool(),
        AgentRuntimeSandbox(tmp_path),
    )
    assert client.features() == {
        AIClientFeature.GENERATION,
        AIClientFeature.MODEL_LISTING,
    }
    monkeypatch.delenv(GITHUB_COPILOT_CLIENT_ID_ENV, raising=False)
    assert resolve_github_copilot_client_id() == GITHUB_COPILOT_CLIENT_ID
    monkeypatch.setenv(GITHUB_COPILOT_CLIENT_ID_ENV, "  Iv1.custom  ")
    assert resolve_github_copilot_client_id() == "Iv1.custom"


class TestDeviceAuthorization:
    @pytest.mark.asyncio
    async def test_start_prefetches_runtime(self, env):
        env.device_flow.start.return_value = "authorization"

        assert await env.client.start_device_authorization({}) == "authorization"
        assert env.provisioner.prefetched == 1

    @pytest.mark.asyncio
    async def test_poll_delegates(self, env):
        env.device_flow.poll.return_value = "pending"

        assert await env.client.poll_device_authorization("flow") == "pending"
        env.device_flow.poll.assert_awaited_once_with("flow")


class TestSetup:
    @pytest.mark.asyncio
    async def test_success_starts_runtime_and_caches_catalog(self, env):
        await env.client.setup(CREDENTIALS)

        executable, token, dirs = env.started[0]
        assert (executable, token) == (EXECUTABLE, TOKEN)
        assert dirs.root.parent == env.tmp_path / "github_copilot" / "instances"

        model = await env.client.get_model("gpt-5-mini", CREDENTIALS)
        assert model.id == "gpt-5-mini"
        assert env.list_calls == 1
        assert len(env.runtimes) == 1

    @pytest.mark.asyncio
    async def test_missing_token_is_invalid(self, env):
        await _setup_error(env, IntegrationSetupErrorCode.INVALID_CREDENTIALS, {})
        assert env.started == []

    @pytest.mark.asyncio
    async def test_unauthenticated_token_is_invalid_and_runtime_stopped(self, env):
        env.authenticated = False

        await _setup_error(env, IntegrationSetupErrorCode.INVALID_CREDENTIALS)

        assert env.runtimes[0].stopped

    @pytest.mark.asyncio
    async def test_account_without_enabled_models_is_not_entitled(self, env):
        env.models = [CopilotModelEntry(id="x", name="X", enabled=False)]

        await _setup_error(env, IntegrationSetupErrorCode.NOT_ENTITLED)

        assert env.runtimes[0].stopped

    @pytest.mark.asyncio
    async def test_runtime_download_failure(self, env):
        env.provisioner.error = CopilotRuntimeUnavailable("offline")

        await _setup_error(env, IntegrationSetupErrorCode.RUNTIME_FAILED)

    @pytest.mark.parametrize(
        "kind, code",
        [
            (CopilotErrorKind.AUTH, IntegrationSetupErrorCode.INVALID_CREDENTIALS),
            (CopilotErrorKind.FORBIDDEN, IntegrationSetupErrorCode.NOT_ENTITLED),
            (CopilotErrorKind.RUNTIME, IntegrationSetupErrorCode.RUNTIME_FAILED),
            (CopilotErrorKind.UNAVAILABLE, IntegrationSetupErrorCode.UNREACHABLE),
        ],
    )
    @pytest.mark.asyncio
    async def test_runtime_errors_are_mapped(self, env, kind, code):
        env.list_error = CopilotRuntimeError(kind, "failed")

        await _setup_error(env, code)

        assert env.runtimes[0].stopped

    @pytest.mark.asyncio
    async def test_factory_failure_removes_instance_dirs(self, env):
        env.factory_error = CopilotRuntimeError(CopilotErrorKind.RUNTIME, "spawn")

        await _setup_error(env, IntegrationSetupErrorCode.RUNTIME_FAILED)

        assert not env.started[0][2].root.exists()

    @pytest.mark.asyncio
    async def test_teardown_stops_runtime_and_clears_catalog(self, env):
        await env.client.setup(CREDENTIALS)

        await env.client.teardown()

        assert env.runtimes[0].stopped
        await env.client.get_model("gpt-5-mini", CREDENTIALS)
        assert env.list_calls == 2
        assert len(env.runtimes) == 2


class TestModels:
    @pytest.mark.asyncio
    async def test_list_models_is_fresh_and_only_enabled(self, env):
        first = await env.client.list_models(CREDENTIALS)
        second = await env.client.list_models(CREDENTIALS)

        assert env.list_calls == 2
        assert first == second
        assert [model.id for model in first] == [
            "gpt-5-mini",
            "claude-sonnet",
            "o-high",
        ]
        mini, sonnet, _ = first
        assert mini.capabilities == {AIModelCapability.STRUCTURED_OUTPUT}
        assert mini.pricing == MINI_PRICING
        assert sonnet.capabilities == {
            AIModelCapability.STRUCTURED_OUTPUT,
            AIModelCapability.REASONING,
        }
        assert sonnet.pricing is None

    @pytest.mark.asyncio
    async def test_get_model_uses_ttl_catalog(self, env):
        assert await env.client.get_model("gpt-5-mini", CREDENTIALS)
        env.clock.now = CATALOG_TTL_SECONDS - 1
        assert await env.client.get_model("claude-sonnet", CREDENTIALS)
        assert env.list_calls == 1

        env.clock.now = CATALOG_TTL_SECONDS
        assert await env.client.get_model("disabled-model", CREDENTIALS) is None
        assert env.list_calls == 2

    @pytest.mark.asyncio
    async def test_missing_credentials(self, env):
        await _provider_error(
            env.client.list_models(None), AIProviderErrorCode.INVALID_CREDENTIALS
        )

    @pytest.mark.asyncio
    async def test_listing_failures_are_mapped(self, env):
        env.provisioner.error = CopilotRuntimeUnavailable("offline")
        await _provider_error(
            env.client.list_models(CREDENTIALS), AIProviderErrorCode.UNAVAILABLE
        )

        env.provisioner.error = None
        env.list_error = CopilotRuntimeError(CopilotErrorKind.AUTH, "revoked")
        await _provider_error(
            env.client.get_model("gpt-5-mini", CREDENTIALS),
            AIProviderErrorCode.INVALID_CREDENTIALS,
        )
        assert env.runtimes[0].stopped


class TestGenerate:
    @pytest.mark.asyncio
    async def test_sends_locked_down_request(self, env):
        result = await env.client.generate(
            _request(reasoning_effort=AIReasoningEffort.HIGH), CREDENTIALS
        )

        assert result.status == AIGenerationStatus.COMPLETED
        assert result.text == '{"labels": []}'
        assert env.completions == [
            {
                "model": "claude-sonnet",
                "instructions": "Label movements",
                "prompt": "first\n\nsecond",
                "schema": SCHEMA,
                "reasoning_effort": "high",
                "timeout": GENERATION_TIMEOUT_SECONDS,
            }
        ]

    @pytest.mark.parametrize(
        "model, requested, expected",
        [
            ("claude-sonnet", AIReasoningEffort.EXTRA_HIGH, "low"),
            ("claude-sonnet", None, "low"),
            ("o-high", AIReasoningEffort.NONE, "high"),
            ("gpt-5-mini", AIReasoningEffort.HIGH, None),
        ],
    )
    @pytest.mark.asyncio
    async def test_reasoning_effort_falls_back_to_supported(
        self, env, model, requested, expected
    ):
        await env.client.generate(
            _request(model=model, reasoning_effort=requested), CREDENTIALS
        )

        assert env.completions[0]["reasoning_effort"] == expected

    @pytest.mark.asyncio
    async def test_empty_reply_is_incomplete(self, env):
        env.text = None

        result = await env.client.generate(_request(), CREDENTIALS)

        assert result.status == AIGenerationStatus.INCOMPLETE

    @pytest.mark.asyncio
    async def test_delisted_model_is_not_sent(self, env):
        await _provider_error(
            env.client.generate(_request(model="disabled-model"), CREDENTIALS),
            AIProviderErrorCode.MODEL_NOT_FOUND,
        )
        assert env.completions == []

    @pytest.mark.parametrize(
        "kind, code, stops_runtime",
        [
            (CopilotErrorKind.AUTH, AIProviderErrorCode.INVALID_CREDENTIALS, True),
            (CopilotErrorKind.FORBIDDEN, AIProviderErrorCode.INVALID_CREDENTIALS, True),
            (CopilotErrorKind.QUOTA, AIProviderErrorCode.INSUFFICIENT_FUNDS, False),
            (CopilotErrorKind.SCHEMA, AIProviderErrorCode.UNSUPPORTED_OPERATION, False),
            (CopilotErrorKind.RUNTIME, AIProviderErrorCode.UNAVAILABLE, True),
            (CopilotErrorKind.RATE_LIMIT, AIProviderErrorCode.UNAVAILABLE, False),
            (CopilotErrorKind.UNAVAILABLE, AIProviderErrorCode.UNAVAILABLE, False),
        ],
    )
    @pytest.mark.asyncio
    async def test_errors_are_mapped(self, env, kind, code, stops_runtime):
        env.complete_error = CopilotRuntimeError(kind, "failed")

        await _provider_error(env.client.generate(_request(), CREDENTIALS), code)

        assert env.runtimes[0].stopped is stops_runtime

    @pytest.mark.asyncio
    async def test_model_error_refreshes_catalog(self, env):
        env.complete_error = CopilotRuntimeError(CopilotErrorKind.MODEL, "gone")

        await _provider_error(
            env.client.generate(_request(), CREDENTIALS),
            AIProviderErrorCode.MODEL_NOT_FOUND,
        )

        env.models = [MODELS[0]]
        env.complete_error = None
        await _provider_error(
            env.client.generate(_request(), CREDENTIALS),
            AIProviderErrorCode.MODEL_NOT_FOUND,
        )
        assert env.list_calls == 2
        assert len(env.completions) == 1
