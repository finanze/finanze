import asyncio
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from infrastructure.client.ai.claude_agent.claude_agent_types import (
    ISOLATION_ARGUMENTS,
    ClaudeAgentError,
    ClaudeErrorKind,
    ClaudeModelEntry,
    claude_environment,
)
from infrastructure.client.ai.claude_agent.claude_cli_runtime import (
    STREAM_LIMIT_BYTES,
    terminate_process,
)
from infrastructure.client.ai.reasoning_levels import REASONING_LEVEL_ORDER

DISCOVERY_TIMEOUT_SECONDS = 30
DEFAULT_OPTION = "default"


def _effort_levels(option: dict) -> tuple[str, ...]:
    levels = option.get("supportedEffortLevels")
    if not isinstance(levels, list):
        return ()
    return tuple(level for level in REASONING_LEVEL_ORDER if level in levels)


def _entries(body: Any) -> list[ClaudeModelEntry]:
    options = body.get("models") if isinstance(body, dict) else None
    if not isinstance(options, list):
        raise ClaudeAgentError(
            ClaudeErrorKind.RUNTIME, "Claude Code did not list its models"
        )

    entries: dict[str, ClaudeModelEntry] = {}
    default_only: set[str] = set()
    for option in options:
        if not isinstance(option, dict):
            continue
        resolved = option.get("resolvedModel")
        model_id = resolved.strip() if isinstance(resolved, str) else ""
        if not model_id:
            continue
        display = option.get("displayName")
        name = display.strip() if isinstance(display, str) else ""
        is_default = option.get("value") == DEFAULT_OPTION

        existing = entries.get(model_id)
        if existing is not None:
            if not is_default and model_id in default_only and name:
                default_only.discard(model_id)
                entries[model_id] = replace(existing, name=name)
            continue
        if is_default:
            default_only.add(model_id)
        entries[model_id] = ClaudeModelEntry(
            id=model_id, name=name or model_id, effort_levels=_effort_levels(option)
        )

    # The "default" option is labelled as a recommendation, not as the model it runs.
    for model_id in default_only:
        entries[model_id] = replace(entries[model_id], name=model_id)
    return list(entries.values())


async def _initialize(process: asyncio.subprocess.Process) -> Any:
    request_id = uuid4().hex
    request = {
        "type": "control_request",
        "request_id": request_id,
        "request": {"subtype": "initialize", "hooks": {}},
    }
    try:
        process.stdin.write((json.dumps(request) + "\n").encode())
        await process.stdin.drain()
    except (BrokenPipeError, ConnectionResetError) as e:
        raise ClaudeAgentError(
            ClaudeErrorKind.RUNTIME, "Claude Code closed before listing its models"
        ) from e

    while True:
        try:
            line = await process.stdout.readline()
        except ValueError as e:
            raise ClaudeAgentError(
                ClaudeErrorKind.RUNTIME, "Claude Code output was too large"
            ) from e
        if not line:
            raise ClaudeAgentError(
                ClaudeErrorKind.RUNTIME, "Claude Code exited before listing its models"
            )
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if not isinstance(message, dict) or message.get("type") != "control_response":
            continue
        response = message.get("response")
        if not isinstance(response, dict) or response.get("request_id") != request_id:
            continue
        if response.get("subtype") != "success":
            raise ClaudeAgentError(
                ClaudeErrorKind.RUNTIME,
                f"Claude Code could not list its models: {response.get('error')}",
            )
        return response.get("response")


class ClaudeModelDiscovery:
    # Reads Claude Code's own model menu without starting a turn, so it uses no plan usage.
    async def discover(self, executable: str, cwd: Path) -> list[ClaudeModelEntry]:
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                "-p",
                "--input-format",
                "stream-json",
                "--output-format",
                "stream-json",
                "--verbose",
                "--no-session-persistence",
                "--permission-prompt-tool",
                "stdio",
                *ISOLATION_ARGUMENTS,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=str(cwd),
                env=claude_environment(),
                limit=STREAM_LIMIT_BYTES,
                start_new_session=os.name != "nt",
            )
        except OSError as e:
            raise ClaudeAgentError(
                ClaudeErrorKind.RUNTIME, "Claude Code could not be started"
            ) from e

        try:
            async with asyncio.timeout(DISCOVERY_TIMEOUT_SECONDS):
                body = await _initialize(process)
        except TimeoutError as e:
            raise ClaudeAgentError(
                ClaudeErrorKind.TIMEOUT, "Claude Code did not list its models in time"
            ) from e
        finally:
            await terminate_process(process)
        return _entries(body)
