import asyncio
import json
import logging
import os
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from infrastructure.agent_runtime.runtime_sandbox import AgentRuntimeInstanceDirs
from infrastructure.client.ai.claude_agent.claude_agent_types import (
    ISOLATION_ARGUMENTS,
    ClaudeAgentError,
    ClaudeCompletion,
    ClaudeErrorKind,
    ClaudeOutcome,
    claude_environment,
    classify_claude_error,
)

MAX_TURNS = 5
MAX_BUDGET_USD = "1.00"
STREAM_LIMIT_BYTES = 16 * 1024 * 1024
STDERR_LIMIT_BYTES = 2048
TERMINATE_GRACE_SECONDS = 5
INCOMPLETE_SUBTYPES = {
    "error_max_turns",
    "error_max_budget_usd",
    "error_max_structured_output_retries",
}
RUN_ENV = {
    "CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1",
    "CLAUDE_CODE_MAX_RETRIES": "3",
    "MAX_STRUCTURED_OUTPUT_RETRIES": "3",
    "CLAUDE_CODE_STARTUP_FAILURE_RESULTS": "1",
}
ERROR_MESSAGES = {
    ClaudeErrorKind.AUTH: "Claude Code is not signed in",
    ClaudeErrorKind.BILLING: "Claude usage credits or spend limit reached",
    ClaudeErrorKind.RATE_LIMIT: "Claude usage limit reached",
    ClaudeErrorKind.MODEL: "The selected Claude model is not available",
    ClaudeErrorKind.CLI_OUTDATED: "Claude Code is too old for the selected model",
    ClaudeErrorKind.OVERLOADED: "Claude is overloaded",
    ClaudeErrorKind.INVALID_REQUEST: "Claude rejected the request",
}

_log = logging.getLogger(__name__)


@dataclass
class _RunState:
    assistant_error: Optional[str] = None
    retry_error: Optional[str] = None
    retry_status: Optional[int] = None
    result: Optional[dict] = None


def _as_int(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _consume(state: _RunState, line: bytes):
    try:
        message = json.loads(line)
    except ValueError:
        return
    if not isinstance(message, dict):
        return

    kind = message.get("type")
    if kind == "system":
        if message.get("subtype") == "api_retry":
            error = message.get("error")
            state.retry_error = error if isinstance(error, str) else None
            state.retry_status = _as_int(message.get("error_status"))
    elif kind == "assistant":
        error = message.get("error")
        if isinstance(error, str):
            state.assistant_error = error
    elif kind == "result":
        state.result = message


async def _read_limited(stream: asyncio.StreamReader, limit: int) -> str:
    kept = bytearray()
    while chunk := await stream.read(65536):
        if len(kept) < limit:
            kept += chunk[: limit - len(kept)]
    return kept.decode(errors="replace")


def _signal(process: asyncio.subprocess.Process, sig: int):
    try:
        if os.name == "nt":
            if sig == signal.SIGTERM:
                process.terminate()
            else:
                process.kill()
        else:
            os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass


async def terminate_process(process: asyncio.subprocess.Process):
    if process.returncode is not None:
        return
    _signal(process, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), TERMINATE_GRACE_SECONDS)
    except TimeoutError:
        _signal(process, getattr(signal, "SIGKILL", signal.SIGTERM))
        await process.wait()


def _usage(result: dict) -> tuple[Optional[int], Optional[int]]:
    usage = result.get("usage")
    if not isinstance(usage, dict):
        return None, None
    return _as_int(usage.get("input_tokens")), _as_int(usage.get("output_tokens"))


def _stdin_payload(prompt: str, attachments: Optional[list[dict]]) -> bytes:
    if not attachments:
        return prompt.encode()
    content = [{"type": "text", "text": prompt}] if prompt else []
    message = {
        "type": "user",
        "message": {"role": "user", "content": content + attachments},
    }
    return (json.dumps(message) + "\n").encode()


class ClaudeCliRuntime:
    def __init__(
        self,
        executable: str,
        dirs: AgentRuntimeInstanceDirs,
        client_app: str,
    ):
        self._executable = executable
        self._dirs = dirs
        self._client_app = client_app
        self._tmp_dir = dirs.root / "tmp"
        self._tmp_dir.mkdir(mode=0o700, exist_ok=True)
        self._processes: set[asyncio.subprocess.Process] = set()

    async def complete(
        self,
        model: str,
        instructions: Optional[str],
        prompt: str,
        schema: Optional[dict],
        effort: Optional[str],
        timeout: float,
        attachments: Optional[list[dict]] = None,
    ) -> ClaudeCompletion:
        system_prompt = self._write_system_prompt(instructions or "")
        try:
            process = await asyncio.create_subprocess_exec(
                *self._arguments(
                    model, system_prompt, schema, effort, bool(attachments)
                ),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._dirs.work),
                env=self._environment(),
                limit=STREAM_LIMIT_BYTES,
                start_new_session=os.name != "nt",
            )
        except OSError as e:
            system_prompt.unlink(missing_ok=True)
            raise ClaudeAgentError(
                ClaudeErrorKind.RUNTIME, "Claude Code could not be started"
            ) from e

        self._processes.add(process)
        try:
            async with asyncio.timeout(timeout):
                state, stderr = await self._run(
                    process, _stdin_payload(prompt, attachments)
                )
        except TimeoutError as e:
            await terminate_process(process)
            raise ClaudeAgentError(
                ClaudeErrorKind.TIMEOUT, "Claude Code did not answer in time"
            ) from e
        except BaseException:
            await terminate_process(process)
            raise
        finally:
            self._processes.discard(process)
            system_prompt.unlink(missing_ok=True)

        return self._completion(state, process.returncode, stderr, schema is not None)

    async def stop(self):
        await asyncio.gather(
            *(terminate_process(process) for process in list(self._processes)),
            return_exceptions=True,
        )
        await self._dirs.remove()

    def _write_system_prompt(self, instructions: str) -> Path:
        path = self._dirs.work / f"system-{uuid4().hex}.txt"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(instructions)
        return path

    def _arguments(
        self,
        model: str,
        system_prompt: Path,
        schema: Optional[dict],
        effort: Optional[str],
        stream_input: bool = False,
    ) -> list[str]:
        arguments = [
            self._executable,
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--no-session-persistence",
            *ISOLATION_ARGUMENTS,
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
            model,
            "--system-prompt-file",
            str(system_prompt),
        ]
        if effort:
            arguments += ["--effort", effort]
        if stream_input:
            arguments += ["--input-format", "stream-json"]
        if schema is not None:
            arguments += ["--json-schema", json.dumps(schema, separators=(",", ":"))]
        return arguments

    def _environment(self) -> dict[str, str]:
        env = claude_environment()
        env.update(RUN_ENV)
        env["CLAUDE_CODE_TMPDIR"] = str(self._tmp_dir)
        env["CLAUDE_AGENT_SDK_CLIENT_APP"] = self._client_app
        return env

    async def _run(
        self, process: asyncio.subprocess.Process, payload: bytes
    ) -> tuple[_RunState, str]:
        stderr_task = asyncio.create_task(
            _read_limited(process.stderr, STDERR_LIMIT_BYTES)
        )
        try:
            try:
                process.stdin.write(payload)
                await process.stdin.drain()
                process.stdin.close()
            except (BrokenPipeError, ConnectionResetError):
                pass

            state = _RunState()
            while True:
                try:
                    line = await process.stdout.readline()
                except ValueError as e:
                    raise ClaudeAgentError(
                        ClaudeErrorKind.RUNTIME, "Claude Code output was too large"
                    ) from e
                if not line:
                    break
                _consume(state, line)

            await process.wait()
            return state, await stderr_task
        finally:
            if not stderr_task.done():
                stderr_task.cancel()

    @staticmethod
    def _completion(
        state: _RunState, returncode: Optional[int], stderr: str, structured: bool
    ) -> ClaudeCompletion:
        result = state.result
        if result is None:
            _log.warning(
                f"Claude Code exited with {returncode} without a result: {stderr}"
            )
            kind = classify_claude_error(
                state.assistant_error or state.retry_error, state.retry_status, stderr
            )
            raise ClaudeAgentError(
                kind, ERROR_MESSAGES.get(kind, "Claude Code ended without a result")
            )

        subtype = result.get("subtype")
        input_tokens, output_tokens = _usage(result)
        if subtype in INCOMPLETE_SUBTYPES:
            return ClaudeCompletion(
                ClaudeOutcome.INCOMPLETE,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        text = result.get("result")
        text = text if isinstance(text, str) else None
        if subtype == "success" and result.get("is_error") is not True:
            output = result.get("structured_output") if structured else text
            if output:
                return ClaudeCompletion(
                    ClaudeOutcome.COMPLETED,
                    text=json.dumps(output) if structured else output,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            outcome = (
                ClaudeOutcome.REFUSED
                if result.get("stop_reason") == "refusal"
                else ClaudeOutcome.INCOMPLETE
            )
            return ClaudeCompletion(
                outcome,
                text=text if outcome == ClaudeOutcome.REFUSED else None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        errors = result.get("errors")
        details = [text or "", str(result.get("startup_failure_reason") or "")]
        if isinstance(errors, list):
            details += [error for error in errors if isinstance(error, str)]
        status = _as_int(result.get("api_error_status")) or state.retry_status
        category = state.assistant_error or state.retry_error
        kind = classify_claude_error(category, status, " ".join(details))
        _log.warning(
            f"Claude Code run failed: subtype={subtype} status={status} error={category} kind={kind.value}"
        )
        if kind == ClaudeErrorKind.RUNTIME and category == "max_output_tokens":
            return ClaudeCompletion(
                ClaudeOutcome.INCOMPLETE,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        raise ClaudeAgentError(kind, ERROR_MESSAGES.get(kind, "Claude Code run failed"))
