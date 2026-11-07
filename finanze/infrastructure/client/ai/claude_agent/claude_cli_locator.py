import asyncio
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from infrastructure.client.ai.claude_agent.claude_agent_types import (
    ClaudeAgentError,
    ClaudeErrorKind,
    claude_environment,
)

CLI_PATH_ENV = "FINANZE_CLAUDE_CLI_PATH"
# Oldest release that knows every current model (Haiku 5.5) and all flags we pass.
MIN_CLAUDE_CODE_VERSION = (2, 1, 293)
VERSION_TIMEOUT_SECONDS = 10
AUTH_STATUS_TIMEOUT_SECONDS = 15
EXECUTABLE_NAMES = ("claude", "claude.exe")
VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True)
class ClaudeCli:
    executable: str
    version: str


class ClaudeCliNotFound(Exception):
    pass


class ClaudeCliOutdated(Exception):
    def __init__(self, version: str):
        self.version = version
        super().__init__(f"Claude Code {version} is too old")


def _is_executable(path: Path) -> bool:
    return (
        path.name.casefold() in EXECUTABLE_NAMES
        and path.is_file()
        and os.access(path, os.X_OK)
    )


def _known_paths() -> list[Path]:
    home = Path.home()
    if os.name == "nt":
        paths = [home / ".local" / "bin" / "claude.exe"]
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            paths.append(
                Path(local_app_data) / "Microsoft" / "WinGet" / "Links" / "claude.exe"
            )
        return paths
    return [
        home / ".local" / "bin" / "claude",
        home / ".claude" / "local" / "claude",
        Path("/opt/homebrew/bin/claude"),
        Path("/usr/local/bin/claude"),
        Path("/usr/bin/claude"),
    ]


def _explicit_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute() or not _is_executable(path):
        raise ClaudeCliNotFound(f"{raw} is not a Claude Code executable")
    return path


def _discover() -> Path:
    found = shutil.which("claude")
    candidates = ([Path(found)] if found else []) + _known_paths()
    for candidate in candidates:
        if _is_executable(candidate):
            return candidate
    raise ClaudeCliNotFound("Claude Code is not installed")


def _parse_version(output: str) -> Optional[tuple[int, int, int]]:
    match = VERSION_PATTERN.search(output)
    if match is None:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _auth_method(output: str) -> Optional[str]:
    try:
        status = json.loads(output)
    except ValueError:
        return None
    if not isinstance(status, dict):
        return None
    if status.get("loggedIn") is False:
        return "none"
    method = status.get("authMethod")
    return method if isinstance(method, str) else None


async def _run(path: Path, timeout: float, *args: str) -> tuple[int, str]:
    try:
        process = await asyncio.create_subprocess_exec(
            str(path),
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=claude_environment(),
        )
    except OSError as e:
        raise ClaudeCliNotFound(f"{path} could not be started") from e
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout)
    except TimeoutError as e:
        process.kill()
        await process.wait()
        raise ClaudeAgentError(
            ClaudeErrorKind.TIMEOUT, f"{path} did not answer in time"
        ) from e
    return process.returncode, stdout.decode(errors="replace")


class ClaudeCliLocator:
    def __init__(self):
        self._cache: dict[tuple[str, int], ClaudeCli] = {}

    async def locate(self, cli_path: Optional[str] = None) -> ClaudeCli:
        explicit = (cli_path or "").strip() or os.environ.get(CLI_PATH_ENV, "").strip()
        path = _explicit_path(explicit) if explicit else _discover()
        key = (str(path), path.stat().st_mtime_ns)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        output = await self._version_output(path)
        version = _parse_version(output)
        if version is None:
            raise ClaudeCliNotFound(f"{path} did not report a Claude Code version")
        label = ".".join(str(part) for part in version)
        if version < MIN_CLAUDE_CODE_VERSION:
            raise ClaudeCliOutdated(label)

        cli = ClaudeCli(executable=str(path), version=label)
        self._cache[key] = cli
        return cli

    def invalidate(self):
        self._cache.clear()

    @staticmethod
    async def signed_in(cli: ClaudeCli) -> bool:
        returncode, output = await _run(
            Path(cli.executable), AUTH_STATUS_TIMEOUT_SECONDS, "auth", "status"
        )
        return returncode == 0 and _auth_method(output) != "none"

    @staticmethod
    async def _version_output(path: Path) -> str:
        try:
            returncode, output = await _run(path, VERSION_TIMEOUT_SECONDS, "--version")
        except ClaudeAgentError as e:
            raise ClaudeCliNotFound(str(e)) from e
        if returncode != 0:
            raise ClaudeCliNotFound(f"{path} exited with {returncode}")
        return output
