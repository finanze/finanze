from pathlib import Path

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
    AIReasoningEffort,
    AIUsage,
)
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from infrastructure.agent_runtime.runtime_pool import AgentRuntimePool
from infrastructure.agent_runtime.runtime_sandbox import AgentRuntimeSandbox
from infrastructure.client.ai.claude_agent.claude_agent_client import (
    CATALOG_TTL_SECONDS,
    GENERATION_TIMEOUT_SECONDS,
    ClaudeAgentClient,
)
from infrastructure.client.ai.claude_agent.claude_agent_types import (
    ClaudeAgentError,
    ClaudeCompletion,
    ClaudeErrorKind,
    ClaudeModelEntry,
    ClaudeOutcome,
)
from infrastructure.client.ai.claude_agent.claude_cli_locator import (
    ClaudeCli,
    ClaudeCliNotFound,
    ClaudeCliOutdated,
)

CREDENTIALS: dict = {}
EXECUTABLE = "/usr/local/bin/claude"
SCHEMA = {"type": "object", "properties": {}}
MODELS = [
    ClaudeModelEntry(
        id="claude-haiku-5-5",
        name="Haiku",
        effort_levels=("low", "medium", "high"),
    ),
    ClaudeModelEntry(id="claude-legacy", name="Legacy"),
]
COMPLETED = ClaudeCompletion(
    ClaudeOutcome.COMPLETED, text='{"results": []}', input_tokens=10, output_tokens=5
)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeLocator:
    def __init__(self):
        self.error: Exception | None = None
        self.executable = EXECUTABLE
        self.paths: list = []
        self.invalidations = 0
        self.logged_in = True
        self.auth_error: Exception | None = None
        self.auth_checks: list[ClaudeCli] = []

    async def locate(self, cli_path=None) -> ClaudeCli:
        self.paths.append(cli_path)
        if self.error:
            raise self.error
        return ClaudeCli(executable=self.executable, version="2.1.300")

    async def signed_in(self, cli: ClaudeCli) -> bool:
        self.auth_checks.append(cli)
        if self.auth_error:
            raise self.auth_error
        return self.logged_in

    def invalidate(self):
        self.invalidations += 1


class FakeDiscovery:
    def __init__(self):
        self.models = MODELS
        self.error: Exception | None = None
        self.calls: list[tuple[str, Path]] = []

    async def discover(self, executable: str, cwd: Path):
        assert cwd.is_dir()
        self.calls.append((executable, cwd))
        if self.error:
            raise self.error
        return list(self.models)


class FakeRuntime:
    def __init__(self, env: "Env", executable, dirs):
        self.env = env
        self.executable = executable
        self.dirs = dirs
        self.stopped = False

    async def stop(self):
        self.stopped = True

    async def complete(self, **kwargs):
        self.env.completions.append(kwargs)
        if self.env.complete_error:
            raise self.env.complete_error
        return self.env.completion


class Env:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.clock = Clock()
        self.locator = FakeLocator()
        self.discovery = FakeDiscovery()
        self.pool = AgentRuntimePool()
        self.runtimes: list[FakeRuntime] = []
        self.completions: list[dict] = []
        self.completion = COMPLETED
        self.complete_error: Exception | None = None
        self.client = ClaudeAgentClient(
            self.locator,
            self.discovery,
            self.pool,
            AgentRuntimeSandbox(tmp_path),
            runtime_factory=self.factory,
            clock=self.clock,
        )

    def factory(self, executable, dirs):
        runtime = FakeRuntime(self, executable, dirs)
        self.runtimes.append(runtime)
        return runtime


@pytest_asyncio.fixture
async def env(tmp_path):
    environment = Env(tmp_path)
    yield environment
    await environment.pool.release_all()


def _request(model="claude-haiku-5-5", **kwargs) -> AIGenerationRequest:
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


def test_features(tmp_path):
    client = ClaudeAgentClient(
        FakeLocator(),
        FakeDiscovery(),
        AgentRuntimePool(),
        AgentRuntimeSandbox(tmp_path),
    )
    assert client.features() == {
        AIClientFeature.GENERATION,
        AIClientFeature.MODEL_LISTING,
        AIClientFeature.ATTACHMENTS,
    }


class TestSetup:
    @pytest.mark.asyncio
    async def test_success_checks_cli_login_and_caches_catalog(self, env):
        await env.client.setup({"cli_path": "/opt/claude"})

        assert env.locator.paths == ["/opt/claude"]
        assert [cli.executable for cli in env.locator.auth_checks] == [EXECUTABLE]
        [(executable, cwd)] = env.discovery.calls
        assert executable == EXECUTABLE
        assert cwd.parent.parent == env.tmp_path / "claude_agent" / "instances"
        assert not cwd.exists()
        assert await env.client.get_model("claude-haiku-5-5", CREDENTIALS)
        assert len(env.discovery.calls) == 1
        assert env.runtimes == []

    @pytest.mark.asyncio
    async def test_empty_payload_uses_the_installed_cli(self, env):
        await env.client.setup({})

        assert env.locator.paths == [None]

    @pytest.mark.parametrize(
        "error, code",
        [
            (ClaudeCliNotFound("missing"), IntegrationSetupErrorCode.RUNTIME_NOT_FOUND),
            (ClaudeCliOutdated("2.1.200"), IntegrationSetupErrorCode.RUNTIME_OUTDATED),
        ],
    )
    @pytest.mark.asyncio
    async def test_cli_problems(self, env, error, code):
        env.locator.error = error

        await _setup_error(env, code)

        assert env.locator.auth_checks == []
        assert env.discovery.calls == []

    @pytest.mark.asyncio
    async def test_signed_out_cli_is_not_authenticated(self, env):
        env.locator.logged_in = False

        await _setup_error(env, IntegrationSetupErrorCode.RUNTIME_NOT_AUTHENTICATED)

        assert env.discovery.calls == []

    @pytest.mark.parametrize(
        "error, code",
        [
            (ClaudeCliNotFound("gone"), IntegrationSetupErrorCode.RUNTIME_NOT_FOUND),
            (
                ClaudeAgentError(ClaudeErrorKind.TIMEOUT, "slow"),
                IntegrationSetupErrorCode.UNREACHABLE,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_auth_status_failures(self, env, error, code):
        env.locator.auth_error = error

        await _setup_error(env, code)

    @pytest.mark.asyncio
    async def test_discovery_failure_still_connects_with_aliases(self, env):
        env.discovery.error = ClaudeAgentError(ClaudeErrorKind.TIMEOUT, "slow")

        await env.client.setup(CREDENTIALS)

        assert await env.client.get_model("sonnet", CREDENTIALS)

    @pytest.mark.asyncio
    async def test_teardown_stops_runtime_and_forgets_state(self, env):
        await env.client.generate(_request(), CREDENTIALS)

        await env.client.teardown()

        assert env.runtimes[0].stopped
        assert env.locator.invalidations == 1
        await env.client.get_model("claude-haiku-5-5", CREDENTIALS)
        assert len(env.discovery.calls) == 2


class TestModels:
    @pytest.mark.asyncio
    async def test_list_models_is_fresh(self, env):
        first = await env.client.list_models(CREDENTIALS)
        second = await env.client.list_models(CREDENTIALS)

        assert first == second
        assert len(env.discovery.calls) == 2
        haiku, legacy = first
        assert (haiku.id, haiku.name) == ("claude-haiku-5-5", "Haiku")
        assert haiku.capabilities == {
            AIModelCapability.STRUCTURED_OUTPUT,
            AIModelCapability.REASONING,
        }
        assert legacy.capabilities == {AIModelCapability.STRUCTURED_OUTPUT}
        assert haiku.pricing is None

    @pytest.mark.asyncio
    async def test_get_model_uses_ttl_catalog(self, env):
        assert await env.client.get_model("claude-haiku-5-5", CREDENTIALS)
        env.clock.now = CATALOG_TTL_SECONDS - 1
        assert await env.client.get_model("claude-legacy", CREDENTIALS)
        assert len(env.discovery.calls) == 1

        env.discovery.models = [MODELS[1]]
        env.clock.now = CATALOG_TTL_SECONDS
        assert await env.client.get_model("claude-haiku-5-5", CREDENTIALS) is None
        assert len(env.discovery.calls) == 2

    @pytest.mark.asyncio
    async def test_catalog_is_per_executable(self, env):
        await env.client.get_model("claude-haiku-5-5", CREDENTIALS)
        env.locator.executable = "/opt/homebrew/bin/claude"
        await env.client.get_model("claude-haiku-5-5", CREDENTIALS)

        assert [call[0] for call in env.discovery.calls] == [
            EXECUTABLE,
            "/opt/homebrew/bin/claude",
        ]

    @pytest.mark.asyncio
    async def test_not_connected(self, env):
        await _provider_error(
            env.client.list_models(None),
            AIProviderErrorCode.INVALID_CREDENTIALS,
        )

    @pytest.mark.parametrize(
        "error",
        [ClaudeCliNotFound("missing"), ClaudeCliOutdated("2.1.200")],
    )
    @pytest.mark.asyncio
    async def test_cli_problems_are_unavailable(self, env, error):
        env.locator.error = error

        await _provider_error(
            env.client.list_models(CREDENTIALS), AIProviderErrorCode.UNAVAILABLE
        )

    @pytest.mark.parametrize(
        "error, models",
        [
            (ClaudeAgentError(ClaudeErrorKind.RUNTIME, "broken"), MODELS),
            (None, []),
        ],
    )
    @pytest.mark.asyncio
    async def test_falls_back_to_aliases(self, env, error, models):
        env.discovery.error = error
        env.discovery.models = models

        listed = await env.client.list_models(CREDENTIALS)

        assert [model.id for model in listed] == ["haiku", "sonnet", "opus"]
        assert all(AIModelCapability.REASONING in m.capabilities for m in listed)
        unlisted = await env.client.get_model("claude-sonnet-5-5", CREDENTIALS)
        assert unlisted.id == "claude-sonnet-5-5"
        assert await env.client.get_model("gpt-5", CREDENTIALS) is None

    @pytest.mark.asyncio
    async def test_discovered_catalog_does_not_accept_unlisted_models(self, env):
        assert await env.client.get_model("claude-sonnet-5-5", CREDENTIALS) is None
        assert await env.client.get_model("sonnet", CREDENTIALS) is None


class TestGenerate:
    @pytest.mark.asyncio
    async def test_runs_completion_in_isolated_runtime(self, env):
        result = await env.client.generate(
            _request(reasoning_effort=AIReasoningEffort.HIGH),
            {"cli_path": "/custom/claude"},
        )

        assert result.status == AIGenerationStatus.COMPLETED
        assert result.text == '{"results": []}'
        assert result.usage == AIUsage(input_tokens=10, output_tokens=5)
        assert env.completions == [
            {
                "model": "claude-haiku-5-5",
                "instructions": "Label movements",
                "prompt": "first\n\nsecond",
                "schema": SCHEMA,
                "effort": "high",
                "timeout": GENERATION_TIMEOUT_SECONDS,
            }
        ]
        runtime = env.runtimes[0]
        assert runtime.executable == EXECUTABLE
        assert runtime.dirs.root.parent == env.tmp_path / "claude_agent" / "instances"
        assert env.locator.paths == ["/custom/claude"]
        assert env.locator.auth_checks == []

    @pytest.mark.parametrize(
        "model, requested, expected",
        [
            ("claude-haiku-5-5", None, "low"),
            ("claude-haiku-5-5", AIReasoningEffort.EXTRA_HIGH, "low"),
            ("claude-legacy", AIReasoningEffort.HIGH, None),
        ],
    )
    @pytest.mark.asyncio
    async def test_effort_falls_back_to_supported(
        self, env, model, requested, expected
    ):
        await env.client.generate(
            _request(model=model, reasoning_effort=requested), CREDENTIALS
        )

        assert env.completions[0]["effort"] == expected

    @pytest.mark.parametrize(
        "model, requested, expected",
        [
            ("sonnet", AIReasoningEffort.HIGH, "high"),
            ("claude-sonnet-5-5", None, "low"),
        ],
    )
    @pytest.mark.asyncio
    async def test_fallback_catalog_runs_aliases_and_claude_ids(
        self, env, model, requested, expected
    ):
        env.discovery.error = ClaudeAgentError(ClaudeErrorKind.RUNTIME, "broken")

        result = await env.client.generate(
            _request(model=model, reasoning_effort=requested), CREDENTIALS
        )

        assert result.status == AIGenerationStatus.COMPLETED
        assert (env.completions[0]["model"], env.completions[0]["effort"]) == (
            model,
            expected,
        )

    @pytest.mark.asyncio
    async def test_reuses_runtime_until_the_executable_changes(self, env):
        await env.client.generate(_request(), CREDENTIALS)
        await env.client.generate(_request(), CREDENTIALS)
        assert len(env.runtimes) == 1

        env.locator.executable = "/opt/homebrew/bin/claude"
        await env.client.generate(_request(), CREDENTIALS)

        assert len(env.runtimes) == 2
        assert env.runtimes[0].stopped

    @pytest.mark.parametrize(
        "completion, status",
        [
            (
                ClaudeCompletion(ClaudeOutcome.REFUSED, text="No"),
                AIGenerationStatus.REFUSED,
            ),
            (ClaudeCompletion(ClaudeOutcome.INCOMPLETE), AIGenerationStatus.INCOMPLETE),
            (ClaudeCompletion(ClaudeOutcome.COMPLETED), AIGenerationStatus.INCOMPLETE),
        ],
    )
    @pytest.mark.asyncio
    async def test_unfinished_completions(self, env, completion, status):
        env.completion = completion

        result = await env.client.generate(_request(), CREDENTIALS)

        assert result.status == status
        assert result.usage is None
        if status == AIGenerationStatus.REFUSED:
            assert result.refusal == "No"

    @pytest.mark.asyncio
    async def test_unknown_model_is_not_sent(self, env):
        await _provider_error(
            env.client.generate(_request(model="claude-retired"), CREDENTIALS),
            AIProviderErrorCode.MODEL_NOT_FOUND,
        )
        assert env.runtimes == []

    @pytest.mark.parametrize(
        "error",
        [ClaudeCliNotFound("missing"), ClaudeCliOutdated("2.1.200")],
    )
    @pytest.mark.asyncio
    async def test_cli_problems_are_unavailable(self, env, error):
        env.locator.error = error

        await _provider_error(
            env.client.generate(_request(), CREDENTIALS),
            AIProviderErrorCode.UNAVAILABLE,
        )
        assert env.runtimes == []

    @pytest.mark.parametrize(
        "kind, code, stops_runtime",
        [
            (ClaudeErrorKind.AUTH, AIProviderErrorCode.INVALID_CREDENTIALS, True),
            (ClaudeErrorKind.BILLING, AIProviderErrorCode.INSUFFICIENT_FUNDS, False),
            (ClaudeErrorKind.RATE_LIMIT, AIProviderErrorCode.UNAVAILABLE, False),
            (ClaudeErrorKind.OVERLOADED, AIProviderErrorCode.UNAVAILABLE, False),
            (ClaudeErrorKind.INVALID_REQUEST, AIProviderErrorCode.UNAVAILABLE, False),
            (ClaudeErrorKind.TIMEOUT, AIProviderErrorCode.UNAVAILABLE, False),
            (ClaudeErrorKind.RUNTIME, AIProviderErrorCode.UNAVAILABLE, True),
        ],
    )
    @pytest.mark.asyncio
    async def test_errors_are_mapped(self, env, kind, code, stops_runtime):
        env.complete_error = ClaudeAgentError(kind, "failed")

        await _provider_error(env.client.generate(_request(), CREDENTIALS), code)

        assert env.runtimes[0].stopped is stops_runtime

    @pytest.mark.asyncio
    async def test_model_error_refreshes_catalog(self, env):
        env.complete_error = ClaudeAgentError(ClaudeErrorKind.MODEL, "gone")

        await _provider_error(
            env.client.generate(_request(), CREDENTIALS),
            AIProviderErrorCode.MODEL_NOT_FOUND,
        )

        env.discovery.models = [MODELS[1]]
        await _provider_error(
            env.client.generate(_request(), CREDENTIALS),
            AIProviderErrorCode.MODEL_NOT_FOUND,
        )
        assert len(env.discovery.calls) == 2
        assert len(env.completions) == 1

    @pytest.mark.asyncio
    async def test_outdated_cli_error_rechecks_the_cli(self, env):
        env.complete_error = ClaudeAgentError(ClaudeErrorKind.CLI_OUTDATED, "old")

        await _provider_error(
            env.client.generate(_request(), CREDENTIALS),
            AIProviderErrorCode.UNAVAILABLE,
        )

        assert env.locator.invalidations == 1
