import asyncio
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from infrastructure.agent_runtime.runtime_sandbox import AgentRuntimeSandbox
from infrastructure.client.ai.claude_agent import claude_cli_runtime
from infrastructure.client.ai.claude_agent.claude_agent_types import (
    ClaudeAgentError,
    ClaudeCompletion,
    ClaudeErrorKind,
    ClaudeOutcome,
    classify_claude_error,
)
from infrastructure.client.ai.claude_agent.claude_cli_runtime import (
    MAX_BUDGET_USD,
    MAX_TURNS,
    ClaudeCliRuntime,
    _read_limited,
)

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX fake executables")

SCHEMA = {"type": "object", "properties": {}}
INIT = {
    "type": "system",
    "subtype": "init",
    "apiKeySource": "none",
    "model": "claude-haiku-5-5",
}
FAKE_CLAUDE = f"""#!{sys.executable}
import json, os, sys, time
from pathlib import Path

scenario = json.loads(Path(os.environ["FAKE_CLAUDE_SCENARIO"]).read_text())
args = sys.argv[1:]
record = {{"argv": args, "cwd": os.getcwd(), "env": dict(os.environ), "stdin": sys.stdin.read()}}
if "--system-prompt-file" in args:
    prompt_file = args[args.index("--system-prompt-file") + 1]
    record["system_prompt"] = Path(prompt_file).read_text()
    record["system_prompt_mode"] = os.stat(prompt_file).st_mode & 0o777
Path(os.environ["FAKE_CLAUDE_RECORD"]).write_text(json.dumps(record))
for line in scenario.get("lines", []):
    if isinstance(line, dict) and "sleep" in line:
        time.sleep(line["sleep"])
        continue
    sys.stdout.write((line if isinstance(line, str) else json.dumps(line)) + "\\n")
    sys.stdout.flush()
sys.stderr.write(scenario.get("stderr", ""))
sys.exit(scenario.get("exit", 0))
"""


def _result(**overrides) -> dict:
    result = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 120, "output_tokens": 30},
    }
    result.update(overrides)
    return result


def _assistant_error(error: str) -> dict:
    return {"type": "assistant", "error": error}


def _retry(error: str, status: int) -> dict:
    return {
        "type": "system",
        "subtype": "api_retry",
        "error": error,
        "error_status": status,
    }


INCOMPLETE = ClaudeOutcome.INCOMPLETE
DURING_EXECUTION = "error_during_execution"
OUTDATED = (
    "Claude Code 2.1.293 does not support this model; "
    "version 2.1.300 or newer is required"
)


@pytest_asyncio.fixture
async def ctx(tmp_path, monkeypatch):
    script = tmp_path / "bin" / "claude"
    script.parent.mkdir()
    script.write_text(FAKE_CLAUDE)
    script.chmod(0o755)
    scenario = tmp_path / "scenario.json"
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_CLAUDE_SCENARIO", str(scenario))
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(record))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-leak")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://proxy.test")
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("HOME", "/Users/me")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/Users/me/.claude-work")

    dirs = await AgentRuntimeSandbox(tmp_path / "sandbox").create_instance(
        "claude_agent"
    )
    runtime = ClaudeCliRuntime(str(script), dirs, "finanze/test")

    def set_scenario(lines, **extra):
        scenario.write_text(json.dumps({"lines": lines, **extra}))

    yield SimpleNamespace(
        runtime=runtime,
        dirs=dirs,
        record_path=record,
        scenario=set_scenario,
        record=lambda: json.loads(record.read_text()),
    )
    await runtime.stop()


async def _complete(ctx, schema=SCHEMA, effort="low", timeout=30.0):
    return await ctx.runtime.complete(
        model="claude-haiku-5-5",
        instructions="Label movements",
        prompt="movements",
        schema=schema,
        effort=effort,
        timeout=timeout,
    )


async def _expect_error(ctx, kind: ClaudeErrorKind, **kwargs):
    with pytest.raises(ClaudeAgentError) as error:
        await _complete(ctx, **kwargs)
    assert error.value.kind == kind


@pytest.mark.asyncio
async def test_structured_completion_runs_with_the_user_login_only(ctx):
    ctx.scenario(
        [
            INIT,
            {"type": "assistant", "message": {"content": []}},
            "not json",
            _result(structured_output={"results": []}),
        ]
    )

    completion = await _complete(ctx)

    assert completion == ClaudeCompletion(
        ClaudeOutcome.COMPLETED,
        text='{"results": []}',
        input_tokens=120,
        output_tokens=30,
    )
    record = ctx.record()
    argv = record["argv"]
    prompt_file = argv[argv.index("--system-prompt-file") + 1]
    assert argv == [
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--setting-sources",
        "project",
        "--settings",
        '{"disableAllHooks":true,"enabledPlugins":{}}',
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--tools",
        "",
        "--disable-slash-commands",
        "--permission-mode",
        "dontAsk",
        "--permission-prompts",
        "none",
        "--max-turns",
        str(MAX_TURNS),
        "--max-budget-usd",
        MAX_BUDGET_USD,
        "--model",
        "claude-haiku-5-5",
        "--system-prompt-file",
        prompt_file,
        "--effort",
        "low",
        "--json-schema",
        '{"type":"object","properties":{}}',
    ]
    assert Path(prompt_file).parent == ctx.dirs.work
    assert record["system_prompt"] == "Label movements"
    assert record["system_prompt_mode"] == 0o600
    assert not Path(prompt_file).exists()
    assert record["stdin"] == "movements"
    assert Path(record["cwd"]).resolve() == ctx.dirs.work.resolve()

    env = record["env"]
    assert env["HOME"] == "/Users/me"
    assert env["CLAUDE_CONFIG_DIR"] == "/Users/me/.claude-work"
    assert env["CLAUDE_CODE_TMPDIR"] == str(ctx.dirs.root / "tmp")
    assert env["CLAUDE_AGENT_SDK_CLIENT_APP"] == "finanze/test"
    assert env["CLAUDE_CODE_SKIP_PROMPT_HISTORY"] == "1"
    assert env["CLAUDE_CODE_STARTUP_FAILURE_RESULTS"] == "1"
    assert env["MAX_STRUCTURED_OUTPUT_RETRIES"] == "3"
    assert env["DISABLE_AUTOUPDATER"] == "1"
    assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    for leaked in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDECODE",
    ):
        assert leaked not in env


@pytest.mark.asyncio
async def test_plain_text_without_schema_or_effort(ctx):
    ctx.scenario([INIT, _result(result="hello")])

    completion = await _complete(ctx, schema=None, effort=None)

    assert completion.outcome == ClaudeOutcome.COMPLETED
    assert completion.text == "hello"
    argv = ctx.record()["argv"]
    assert "--json-schema" not in argv
    assert "--effort" not in argv


@pytest.mark.parametrize(
    "result, outcome, text",
    [
        (_result(subtype="error_max_turns", is_error=True), INCOMPLETE, None),
        (_result(subtype="error_max_budget_usd", is_error=True), INCOMPLETE, None),
        (
            _result(subtype="error_max_structured_output_retries", is_error=True),
            INCOMPLETE,
            None,
        ),
        (
            _result(stop_reason="refusal", result="Not allowed"),
            ClaudeOutcome.REFUSED,
            "Not allowed",
        ),
        (_result(), INCOMPLETE, None),
    ],
)
@pytest.mark.asyncio
async def test_unfinished_runs(ctx, result, outcome, text):
    ctx.scenario([INIT, result])

    completion = await _complete(ctx)

    assert (completion.outcome, completion.text) == (outcome, text)
    assert completion.input_tokens == 120


@pytest.mark.asyncio
async def test_max_output_tokens_is_incomplete(ctx):
    ctx.scenario([INIT, _assistant_error("max_output_tokens"), _result(is_error=True)])

    assert (await _complete(ctx)).outcome == INCOMPLETE


@pytest.mark.parametrize(
    "lines, kind",
    [
        (
            [
                _assistant_error("authentication_failed"),
                _result(is_error=True, result="Not logged in"),
            ],
            ClaudeErrorKind.AUTH,
        ),
        ([_result(is_error=True, api_error_status=401)], ClaudeErrorKind.AUTH),
        (
            [_assistant_error("billing_error"), _result(is_error=True)],
            ClaudeErrorKind.BILLING,
        ),
        (
            [
                _retry("rate_limit", 429),
                _result(subtype=DURING_EXECUTION, is_error=True, errors=["API"]),
            ],
            ClaudeErrorKind.RATE_LIMIT,
        ),
        (
            [_assistant_error("model_not_found"), _result(is_error=True)],
            ClaudeErrorKind.MODEL,
        ),
        (
            [_result(subtype=DURING_EXECUTION, is_error=True, errors=[OUTDATED])],
            ClaudeErrorKind.CLI_OUTDATED,
        ),
        (
            [
                _result(
                    subtype=DURING_EXECUTION,
                    is_error=True,
                    errors=["Update required"],
                    startup_failure_reason="cli_version_too_old",
                )
            ],
            ClaudeErrorKind.CLI_OUTDATED,
        ),
        (
            [_retry("overloaded", 529), _result(is_error=True)],
            ClaudeErrorKind.OVERLOADED,
        ),
        ([_result(is_error=True)], ClaudeErrorKind.RUNTIME),
    ],
)
@pytest.mark.asyncio
async def test_failed_runs_are_classified(ctx, lines, kind):
    ctx.scenario([INIT, *lines])

    await _expect_error(ctx, kind)


@pytest.mark.asyncio
async def test_exit_without_result_is_a_runtime_error(ctx):
    ctx.scenario([INIT], stderr="error: unknown option '--settings'", exit=1)

    await _expect_error(ctx, ClaudeErrorKind.RUNTIME)


@pytest.mark.asyncio
async def test_timeout_terminates_the_process(ctx):
    ctx.scenario([INIT, {"sleep": 30}])

    started = time.monotonic()
    await _expect_error(ctx, ClaudeErrorKind.TIMEOUT, timeout=0.5)

    assert time.monotonic() - started < 10
    assert ctx.runtime._processes == set()


@pytest.mark.asyncio
async def test_stop_kills_running_calls_and_removes_dirs(ctx):
    ctx.scenario([INIT, {"sleep": 30}])
    call = asyncio.create_task(_complete(ctx))
    for _ in range(200):
        if ctx.record_path.exists() and ctx.runtime._processes:
            break
        await asyncio.sleep(0.05)

    await ctx.runtime.stop()

    with pytest.raises(ClaudeAgentError) as error:
        await asyncio.wait_for(call, 10)
    assert error.value.kind == ClaudeErrorKind.RUNTIME
    assert not ctx.dirs.root.exists()


@pytest.mark.asyncio
async def test_oversized_output_line_fails(ctx, monkeypatch):
    monkeypatch.setattr(claude_cli_runtime, "STREAM_LIMIT_BYTES", 1024)
    ctx.scenario([INIT, "x" * 4096, _result(structured_output={})])

    await _expect_error(ctx, ClaudeErrorKind.RUNTIME)


@pytest.mark.asyncio
async def test_missing_executable_fails_to_start(ctx):
    runtime = ClaudeCliRuntime(
        str(ctx.dirs.root / "missing" / "claude"), ctx.dirs, "finanze/test"
    )

    with pytest.raises(ClaudeAgentError) as error:
        await runtime.complete("model", None, "prompt", None, None, 5)

    assert error.value.kind == ClaudeErrorKind.RUNTIME
    assert list(ctx.dirs.work.glob("system-*")) == []


@pytest.mark.asyncio
async def test_stderr_is_truncated():
    reader = asyncio.StreamReader()
    reader.feed_data(b"a" * 5000)
    reader.feed_eof()

    assert await _read_limited(reader, 10) == "a" * 10


@pytest.mark.parametrize(
    "category, status, text, kind",
    [
        ("invalid_request", 400, "cli_version_too_old", ClaudeErrorKind.CLI_OUTDATED),
        ("oauth_org_not_allowed", None, "", ClaudeErrorKind.AUTH),
        ("account_on_hold", None, "", ClaudeErrorKind.AUTH),
        (None, 403, "", ClaudeErrorKind.AUTH),
        (None, 402, "", ClaudeErrorKind.BILLING),
        ("rate_limit", 429, "Spend limit reached", ClaudeErrorKind.BILLING),
        (None, 429, "", ClaudeErrorKind.RATE_LIMIT),
        (None, 404, "", ClaudeErrorKind.MODEL),
        ("server_error", None, "", ClaudeErrorKind.OVERLOADED),
        (None, 503, "", ClaudeErrorKind.OVERLOADED),
        ("invalid_request", None, "", ClaudeErrorKind.INVALID_REQUEST),
        ("unknown", None, "", ClaudeErrorKind.RUNTIME),
    ],
)
def test_classify_claude_error(category, status, text, kind):
    assert classify_claude_error(category, status, text) == kind
