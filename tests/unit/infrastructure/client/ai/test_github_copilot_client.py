import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from application.ports.external_integration_port import ExternalIntegrationPort
from dateutil.tz import tzlocal
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
from domain.external_integration import ExternalIntegrationId
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
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=tzlocal())
EXPIRES_AT = NOW + timedelta(hours=8)
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


class WallClock:
    def __init__(self):
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def _expiring(access: str, refresh: str, expires_at: datetime = EXPIRES_AT) -> dict:
    return {
        "access_token": access,
        "refresh_token": refresh,
        "expires_at": expires_at.isoformat(),
    }


EXPIRING = _expiring("gho_a", "ghr_a")
REFRESHED = _expiring("gho_b", "ghr_b", EXPIRES_AT + timedelta(hours=8))


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
        if self.env.complete_errors:
            raise self.env.complete_errors.pop(0)
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
        self.complete_errors: list[Exception] = []
        self.factory_error: Exception | None = None
        self.text = '{"labels": []}'
        self.list_calls = 0
        self.completions: list[dict] = []
        self.runtimes: list[FakeRuntime] = []
        self.started: list[tuple] = []
        self.clock = Clock()
        self.wall = WallClock()
        self.provisioner = FakeProvisioner()
        self.device_flow = AsyncMock()
        self.integrations = AsyncMock(spec=ExternalIntegrationPort)
        self.pool = AgentRuntimePool()
        self.sandbox = AgentRuntimeSandbox(tmp_path)
        self.tmp_path = tmp_path
        self.client = GitHubCopilotClient(
            self.device_flow,
            self.provisioner,
            self.pool,
            self.sandbox,
            self.integrations,
            runtime_factory=self.factory,
            clock=self.clock,
            now=self.wall,
        )

    @property
    def tokens(self) -> list[str]:
        return [token for _, token, _ in self.started]

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
        AsyncMock(spec=ExternalIntegrationPort),
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


class TestTokenRefresh:
    @pytest.mark.asyncio
    async def test_token_far_from_expiry_is_not_refreshed(self, env):
        env.wall.now = EXPIRES_AT - timedelta(minutes=6)

        await env.client.generate(_request(), EXPIRING)

        env.device_flow.refresh.assert_not_awaited()
        assert env.tokens == ["gho_a"]

    @pytest.mark.asyncio
    async def test_token_without_refresh_token_is_used_as_is(self, env):
        env.wall.now = EXPIRES_AT + timedelta(hours=1)

        await env.client.generate(
            _request(), {**CREDENTIALS, "expires_at": EXPIRES_AT.isoformat()}
        )

        env.device_flow.refresh.assert_not_awaited()
        assert env.tokens == [TOKEN]

    @pytest.mark.asyncio
    async def test_expiring_token_is_rotated_and_stale_payloads_follow(self, env):
        env.device_flow.refresh.return_value = REFRESHED
        await env.client.generate(_request(), EXPIRING)

        env.wall.now = EXPIRES_AT - timedelta(minutes=4)
        await env.client.generate(_request(), EXPIRING)
        await env.client.generate(_request(), EXPIRING)

        env.device_flow.refresh.assert_awaited_once_with("ghr_a")
        env.integrations.update_payload.assert_awaited_once_with(
            ExternalIntegrationId.GITHUB_COPILOT, REFRESHED
        )
        assert env.tokens == ["gho_a", "gho_b"]
        assert env.runtimes[0].stopped
        assert env.list_calls == 1
        assert len(env.completions) == 3

    @pytest.mark.asyncio
    async def test_concurrent_calls_refresh_once(self, env):
        async def refresh(refresh_token):
            await asyncio.sleep(0)
            return REFRESHED

        env.device_flow.refresh.side_effect = refresh
        env.wall.now = EXPIRES_AT - timedelta(minutes=1)

        await asyncio.gather(
            *(env.client.generate(_request(), EXPIRING) for _ in range(3))
        )

        assert env.device_flow.refresh.await_count == 1
        assert env.integrations.update_payload.await_count == 1
        assert env.tokens == ["gho_b"]

    @pytest.mark.asyncio
    async def test_unreachable_refresh_keeps_still_valid_token(self, env):
        env.device_flow.refresh.side_effect = AIProviderError(
            AIProviderErrorCode.UNAVAILABLE, "offline"
        )
        env.wall.now = EXPIRES_AT - timedelta(minutes=1)

        result = await env.client.generate(_request(), EXPIRING)

        assert result.status == AIGenerationStatus.COMPLETED
        assert env.tokens == ["gho_a"]
        env.integrations.update_payload.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unreachable_refresh_after_expiry_is_unavailable(self, env):
        env.device_flow.refresh.side_effect = AIProviderError(
            AIProviderErrorCode.UNAVAILABLE, "offline"
        )
        env.wall.now = EXPIRES_AT

        await _provider_error(
            env.client.generate(_request(), EXPIRING), AIProviderErrorCode.UNAVAILABLE
        )
        assert env.started == []

    @pytest.mark.asyncio
    async def test_rejected_refresh_is_invalid_credentials(self, env):
        env.device_flow.refresh.side_effect = AIProviderError(
            AIProviderErrorCode.INVALID_CREDENTIALS, "bad_refresh_token"
        )
        env.wall.now = EXPIRES_AT - timedelta(minutes=1)

        await _provider_error(
            env.client.list_models(EXPIRING), AIProviderErrorCode.INVALID_CREDENTIALS
        )
        env.integrations.update_payload.assert_not_awaited()
        assert env.started == []

    @pytest.mark.asyncio
    async def test_auth_error_refreshes_and_retries_once(self, env):
        env.device_flow.refresh.return_value = REFRESHED
        env.complete_errors = [CopilotRuntimeError(CopilotErrorKind.AUTH, "401")]

        result = await env.client.generate(_request(), EXPIRING)

        assert result.status == AIGenerationStatus.COMPLETED
        env.device_flow.refresh.assert_awaited_once_with("ghr_a")
        env.integrations.update_payload.assert_awaited_once_with(
            ExternalIntegrationId.GITHUB_COPILOT, REFRESHED
        )
        assert env.tokens == ["gho_a", "gho_b"]
        assert env.runtimes[0].stopped
        assert len(env.completions) == 2

    @pytest.mark.asyncio
    async def test_repeated_auth_error_is_invalid_credentials(self, env):
        env.device_flow.refresh.return_value = REFRESHED
        env.complete_error = CopilotRuntimeError(CopilotErrorKind.AUTH, "401")

        await _provider_error(
            env.client.generate(_request(), EXPIRING),
            AIProviderErrorCode.INVALID_CREDENTIALS,
        )
        assert env.device_flow.refresh.await_count == 1
        assert all(runtime.stopped for runtime in env.runtimes)

    @pytest.mark.asyncio
    async def test_forbidden_is_not_refreshed(self, env):
        env.complete_error = CopilotRuntimeError(CopilotErrorKind.FORBIDDEN, "403")

        await _provider_error(
            env.client.generate(_request(), EXPIRING),
            AIProviderErrorCode.INVALID_CREDENTIALS,
        )
        env.device_flow.refresh.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_teardown_forgets_rotation(self, env):
        env.device_flow.refresh.return_value = REFRESHED
        env.wall.now = EXPIRES_AT - timedelta(minutes=1)
        await env.client.generate(_request(), EXPIRING)

        await env.client.teardown()
        await env.client.generate(_request(), EXPIRING)

        assert env.device_flow.refresh.await_count == 2
