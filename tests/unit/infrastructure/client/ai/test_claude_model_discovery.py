import json
import os
import sys
import time
from types import SimpleNamespace

import pytest
from infrastructure.client.ai.claude_agent import claude_model_discovery
from infrastructure.client.ai.claude_agent.claude_agent_types import (
    ClaudeAgentError,
    ClaudeErrorKind,
    ClaudeModelEntry,
)
from infrastructure.client.ai.claude_agent.claude_model_discovery import (
    ClaudeModelDiscovery,
)

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX fake executables")

FAKE_CLAUDE = f"""#!{sys.executable}
import json, os, sys, time
from pathlib import Path

scenario = json.loads(Path(os.environ["FAKE_CLAUDE_SCENARIO"]).read_text())
record = {{"argv": sys.argv[1:], "cwd": os.getcwd(), "env": dict(os.environ)}}
Path(os.environ["FAKE_CLAUDE_RECORD"]).write_text(json.dumps(record))
if scenario.get("exit_early"):
    sys.exit(1)
request = json.loads(sys.stdin.readline())
record["request"] = request
Path(os.environ["FAKE_CLAUDE_RECORD"]).write_text(json.dumps(record))
if scenario.get("hang"):
    time.sleep(30)
print(json.dumps({{"type": "system", "subtype": "status"}}))
print("not json")
print(json.dumps({{"type": "control_response", "response": {{"subtype": "success", "request_id": "other"}}}}))
response = {{"subtype": scenario.get("subtype", "success"), "request_id": request["request_id"]}}
if "error" in scenario:
    response["error"] = scenario["error"]
if "body" in scenario:
    response["response"] = scenario["body"]
print(json.dumps({{"type": "control_response", "response": response}}), flush=True)
time.sleep(30)
"""


def _option(value, resolved, name, efforts=None) -> dict:
    option = {"value": value, "resolvedModel": resolved, "displayName": name}
    if efforts is not None:
        option["supportedEffortLevels"] = efforts
    return option


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    script = tmp_path / "bin" / "claude"
    script.parent.mkdir()
    script.write_text(FAKE_CLAUDE)
    script.chmod(0o755)
    work = tmp_path / "work"
    work.mkdir()
    scenario = tmp_path / "scenario.json"
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_CLAUDE_SCENARIO", str(scenario))
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(record))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-leak")
    monkeypatch.setenv("HOME", "/Users/me")

    return SimpleNamespace(
        script=str(script),
        work=work,
        scenario=lambda **values: scenario.write_text(json.dumps(values)),
        record=lambda: json.loads(record.read_text()),
    )


async def _discover(ctx) -> list[ClaudeModelEntry]:
    return await ClaudeModelDiscovery().discover(ctx.script, ctx.work)


@pytest.mark.asyncio
async def test_lists_the_claude_code_model_menu_without_a_turn(ctx):
    ctx.scenario(
        body={
            "models": [
                _option(
                    "default", "claude-sonnet-5-5", "Default (recommended)", ["low"]
                ),
                _option("sonnet", "claude-sonnet-5-5", "Sonnet", ["low", "max"]),
                _option("opus", "claude-opus-5-5", "Opus", ["max", "low", "bogus"]),
                _option("haiku", "claude-haiku-5-5", ""),
                _option("opusplan", "", "Opus Plan Mode"),
                "invalid",
            ]
        }
    )

    entries = await _discover(ctx)

    assert entries == [
        ClaudeModelEntry("claude-sonnet-5-5", "Sonnet", ("low",)),
        ClaudeModelEntry("claude-opus-5-5", "Opus", ("low", "max")),
        ClaudeModelEntry("claude-haiku-5-5", "claude-haiku-5-5", ()),
    ]
    record = ctx.record()
    assert record["request"]["request"] == {"subtype": "initialize", "hooks": {}}
    assert record["argv"] == [
        "-p",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--permission-prompt-tool",
        "stdio",
        "--setting-sources",
        "project",
        "--settings",
        '{"disableAllHooks":true,"enabledPlugins":{}}',
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--tools",
        "",
    ]
    assert os.path.realpath(record["cwd"]) == os.path.realpath(ctx.work)
    assert record["env"]["HOME"] == "/Users/me"
    assert "ANTHROPIC_API_KEY" not in record["env"]


@pytest.mark.asyncio
async def test_default_only_option_is_named_after_its_model(ctx):
    ctx.scenario(
        body={
            "models": [
                _option("default", "claude-future-6", "Default (recommended)"),
            ]
        }
    )

    assert await _discover(ctx) == [
        ClaudeModelEntry("claude-future-6", "claude-future-6", ())
    ]


@pytest.mark.parametrize(
    "scenario",
    [
        {"subtype": "error", "error": "not ready"},
        {"body": {"other": []}},
        {},
        {"exit_early": True},
    ],
)
@pytest.mark.asyncio
async def test_unusable_answers_are_runtime_errors(ctx, scenario):
    ctx.scenario(**scenario)

    started = time.monotonic()
    with pytest.raises(ClaudeAgentError) as error:
        await _discover(ctx)

    assert error.value.kind == ClaudeErrorKind.RUNTIME
    assert time.monotonic() - started < 10


@pytest.mark.asyncio
async def test_silent_cli_times_out(ctx, monkeypatch):
    monkeypatch.setattr(claude_model_discovery, "DISCOVERY_TIMEOUT_SECONDS", 0.5)
    ctx.scenario(hang=True)

    started = time.monotonic()
    with pytest.raises(ClaudeAgentError) as error:
        await _discover(ctx)

    assert error.value.kind == ClaudeErrorKind.TIMEOUT
    assert time.monotonic() - started < 10


@pytest.mark.asyncio
async def test_missing_executable_is_a_runtime_error(ctx):
    with pytest.raises(ClaudeAgentError) as error:
        await ClaudeModelDiscovery().discover(
            str(ctx.work / "missing" / "claude"), ctx.work
        )

    assert error.value.kind == ClaudeErrorKind.RUNTIME
