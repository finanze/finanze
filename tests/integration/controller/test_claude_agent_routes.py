import json
import os
import sqlite3
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from application.use_cases.connect_external_integration import (
    ConnectExternalIntegrationImpl,
)
from application.use_cases.get_external_integrations import (
    GetExternalIntegrationsImpl,
)
from application.use_cases.get_external_labeling_models import (
    GetExternalLabelingModelsImpl,
)
from domain.ai import (
    AIGenerationRequest,
    AIGenerationStatus,
    AIJsonSchema,
    AIMessage,
    AIMessageRole,
)
from domain.data_init import DatasourceInitContext
from domain.external_integration import ExternalIntegrationId
from infrastructure.agent_runtime.runtime_pool import AgentRuntimePool
from infrastructure.agent_runtime.runtime_sandbox import AgentRuntimeSandbox
from infrastructure.client.ai.claude_agent.claude_agent_client import (
    ClaudeAgentClient,
)
from infrastructure.client.ai.claude_agent.claude_cli_locator import (
    CLI_PATH_ENV,
    ClaudeCliLocator,
)
from infrastructure.client.ai.claude_agent.claude_model_discovery import (
    ClaudeModelDiscovery,
)
from infrastructure.controller.config import quart
from infrastructure.controller.exception_handler import register_exception_handlers
from infrastructure.controller.routes.connect_external_integration import (
    connect_external_integration,
)
from infrastructure.controller.routes.get_external_integrations import (
    get_external_integrations,
)
from infrastructure.controller.routes.get_external_labeling_models import (
    get_external_labeling_models,
)
from infrastructure.labeling.ai_labeling_presets import LABELING_PRESETS
from infrastructure.labeling.ai_labeling_provider import AILabelingProvider
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.external_integration.external_integration_repository import (
    ExternalIntegrationRepository,
)

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX fake executables")

CLAUDE = ExternalIntegrationId.CLAUDE_AGENT
FAKE_CLAUDE = f"""#!{sys.executable}
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_CLAUDE_CALLS"], "a") as calls:
    calls.write(" ".join(args[:3]) + "\\n")

if args == ["--version"]:
    print(os.environ.get("FAKE_CLAUDE_VERSION", "2.1.300") + " (Claude Code)")
    sys.exit(0)

if args == ["auth", "status"]:
    if os.environ.get("FAKE_CLAUDE_LOGGED_IN", "1") == "1":
        print(json.dumps({{"loggedIn": True, "authMethod": "claude.ai"}}))
        sys.exit(0)
    print(json.dumps({{"loggedIn": False, "authMethod": "none"}}))
    sys.exit(1)

if "--input-format" in args:
    request = json.loads(sys.stdin.readline())
    print(json.dumps({{"type": "control_response", "response": {{
        "subtype": "success",
        "request_id": request["request_id"],
        "response": {{"models": [
            {{"value": "default", "resolvedModel": "claude-sonnet-5-5", "displayName": "Default (recommended)", "supportedEffortLevels": ["low", "medium", "high", "max"]}},
            {{"value": "sonnet", "resolvedModel": "claude-sonnet-5-5", "displayName": "Sonnet", "supportedEffortLevels": ["low", "medium", "high", "max"]}},
            {{"value": "haiku", "resolvedModel": "claude-haiku-5-5", "displayName": "Haiku", "supportedEffortLevels": ["low", "medium", "high"]}},
        ]}},
    }}}}), flush=True)
    sys.stdin.read()
    sys.exit(0)

prompt = sys.stdin.read()
Path(os.environ["FAKE_CLAUDE_RECORD"]).write_text(json.dumps({{
    "model": args[args.index("--model") + 1],
    "effort": args[args.index("--effort") + 1],
    "prompt": prompt,
    "api_key": os.environ.get("ANTHROPIC_API_KEY"),
    "home": os.environ.get("HOME"),
}}))
print(json.dumps({{"type": "system", "subtype": "init", "apiKeySource": "none"}}))
print(json.dumps({{
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "result": "",
    "structured_output": {{"results": [{{"id": prompt, "category": "food"}}]}},
    "usage": {{"input_tokens": 50, "output_tokens": 8}},
}}))
"""


@pytest_asyncio.fixture
async def ctx(tmp_path, monkeypatch):
    monkeypatch.delenv(CLI_PATH_ENV, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-be-used")
    cli = tmp_path / "bin" / "claude"
    cli.parent.mkdir()
    cli.write_text(FAKE_CLAUDE)
    cli.chmod(0o755)
    record = tmp_path / "record.json"
    calls = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(record))
    monkeypatch.setenv("FAKE_CLAUDE_CALLS", str(calls))

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    client = DBClient(connection)
    await DatabaseUpgrader(
        client, versions, DatasourceInitContext(config=AsyncMock())
    ).upgrade()
    repository = ExternalIntegrationRepository(client)

    pool = AgentRuntimePool()
    claude = ClaudeAgentClient(
        ClaudeCliLocator(),
        ClaudeModelDiscovery(),
        pool,
        AgentRuntimeSandbox(tmp_path / "agent_runtimes"),
        client_app="finanze/test",
    )
    integrations = {CLAUDE: claude}
    get_uc = GetExternalIntegrationsImpl(repository, integrations)
    connect_uc = ConnectExternalIntegrationImpl(repository, integrations)
    models_uc = GetExternalLabelingModelsImpl(
        repository, {CLAUDE: AILabelingProvider(claude, LABELING_PRESETS[CLAUDE])}
    )

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    app = quart(static_dir)
    register_exception_handlers(app)

    @app.route("/api/v1/integrations", methods=["GET"])
    async def get_integrations_route():
        return await get_external_integrations(get_uc)

    @app.route("/api/v1/integrations/<integration_id>", methods=["POST"])
    async def connect_route(integration_id: str):
        return await connect_external_integration(connect_uc, integration_id)

    @app.route(
        "/api/v1/labeling/external/providers/<provider_id>/models", methods=["GET"]
    )
    async def models_route(provider_id: str):
        return await get_external_labeling_models(models_uc, provider_id)

    yield SimpleNamespace(
        http=app.test_client(),
        repository=repository,
        claude=claude,
        cli=cli,
        record=record,
        calls=lambda: calls.read_text().splitlines() if calls.exists() else [],
        sandbox_root=tmp_path / "agent_runtimes",
    )

    await pool.release_all()
    connection.close()


async def _integration(ctx) -> dict:
    response = await ctx.http.get("/api/v1/integrations")
    integrations = (await response.get_json())["integrations"]
    return next(i for i in integrations if i["id"] == CLAUDE.value)


async def _connect(ctx, payload: dict):
    return await ctx.http.post(
        f"/api/v1/integrations/{CLAUDE.value}", json={"payload": payload}
    )


@pytest.mark.asyncio
async def test_connects_lists_models_and_labels_with_signed_in_claude_code(ctx):
    integration = await _integration(ctx)
    assert (integration["name"], integration["type"]) == ("Claude Agent", "AI_PROVIDER")
    assert integration["available"] is True
    assert integration["status"] == "OFF"
    assert integration["payload_schema"] == {"cli_path": "Claude Code path"}
    assert integration["optional_fields"] == ["cli_path"]

    response = await _connect(ctx, {"cli_path": str(ctx.cli)})

    assert response.status_code == 204
    assert (await _integration(ctx))["status"] == "ON"
    credentials = await ctx.repository.get_payload(CLAUDE)
    assert credentials == {"cli_path": str(ctx.cli)}
    assert ctx.calls() == [
        "--version",
        "auth status",
        "-p --input-format stream-json",
    ]

    models = await ctx.http.get(
        f"/api/v1/labeling/external/providers/{CLAUDE.value}/models"
    )
    assert models.status_code == 200
    assert [
        (model["id"], model["name"]) for model in (await models.get_json())["models"]
    ] == [("claude-sonnet-5-5", "Sonnet"), ("claude-haiku-5-5", "Haiku")]

    generation = await ctx.claude.generate(
        AIGenerationRequest(
            model="claude-haiku-5-5",
            messages=[AIMessage(role=AIMessageRole.USER, content="tx-1")],
            instructions="Label movements",
            response_schema=AIJsonSchema(name="labels", schema={"type": "object"}),
        ),
        credentials,
    )

    assert generation.status == AIGenerationStatus.COMPLETED
    assert json.loads(generation.text) == {
        "results": [{"id": "tx-1", "category": "food"}]
    }
    assert json.loads(ctx.record.read_text()) == {
        "model": "claude-haiku-5-5",
        "effort": "low",
        "prompt": "tx-1",
        "api_key": None,
        "home": os.environ["HOME"],
    }
    instances = ctx.sandbox_root / "claude_agent" / "instances"
    assert len(list(instances.iterdir())) == 1


@pytest.mark.asyncio
async def test_connects_without_any_field(ctx, monkeypatch):
    monkeypatch.setenv(CLI_PATH_ENV, str(ctx.cli))

    response = await _connect(ctx, {"cli_path": "  "})

    assert response.status_code == 204
    assert await ctx.repository.get_payload(CLAUDE) == {}


@pytest.mark.asyncio
async def test_signed_out_claude_code_is_rejected(ctx, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_LOGGED_IN", "0")

    response = await _connect(ctx, {"cli_path": str(ctx.cli)})

    assert response.status_code == 400
    assert (await response.get_json())["code"] == "RUNTIME_NOT_AUTHENTICATED"
    assert await ctx.repository.get_payload(CLAUDE) is None
    assert ctx.calls() == ["--version", "auth status"]


@pytest.mark.parametrize(
    "cli_path",
    ["relative/claude", "/nonexistent/claude", "/bin/sh"],
)
@pytest.mark.asyncio
async def test_missing_claude_code_is_rejected(ctx, cli_path):
    response = await _connect(ctx, {"cli_path": cli_path})

    assert response.status_code == 400
    assert (await response.get_json())["code"] == "RUNTIME_NOT_FOUND"
    assert (await _integration(ctx))["status"] == "OFF"
    assert ctx.calls() == []


@pytest.mark.asyncio
async def test_outdated_claude_code_is_rejected(ctx, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_VERSION", "2.1.100")

    response = await _connect(ctx, {"cli_path": str(ctx.cli)})

    assert response.status_code == 400
    assert (await response.get_json())["code"] == "RUNTIME_OUTDATED"
    assert await ctx.repository.get_payload(CLAUDE) is None
