import os
from pathlib import Path

import pytest
from infrastructure.client.ai.claude_agent import claude_cli_locator
from infrastructure.client.ai.claude_agent.claude_cli_locator import (
    CLI_PATH_ENV,
    ClaudeCli,
    ClaudeCliLocator,
    ClaudeCliNotFound,
    ClaudeCliOutdated,
)

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX fake executables")


def _write_cli(
    directory: Path,
    output: str = "2.1.300 (Claude Code)",
    exit_code: int = 0,
    name: str = "claude",
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    calls = directory / "calls.log"
    env_dump = directory / "env.log"
    path.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> "{calls}"\n'
        f'/usr/bin/env > "{env_dump}"\n'
        f"echo '{output}'\n"
        f"exit {exit_code}\n"
    )
    path.chmod(0o755)
    return path


def _calls(directory: Path) -> list[str]:
    calls = directory / "calls.log"
    return calls.read_text().splitlines() if calls.exists() else []


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.delenv(CLI_PATH_ENV, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    monkeypatch.setattr(claude_cli_locator, "_known_paths", lambda: [])


@pytest.mark.asyncio
async def test_explicit_path_reports_version(tmp_path):
    cli = _write_cli(tmp_path / "bin")

    result = await ClaudeCliLocator().locate(str(cli))

    assert result == ClaudeCli(executable=str(cli), version="2.1.300")
    assert _calls(tmp_path / "bin") == ["--version"]


@pytest.mark.asyncio
async def test_env_path_is_used_without_payload_path(monkeypatch, tmp_path):
    cli = _write_cli(tmp_path / "env-bin")
    monkeypatch.setenv(CLI_PATH_ENV, str(cli))

    assert (await ClaudeCliLocator().locate(None)).executable == str(cli)


@pytest.mark.asyncio
async def test_discovers_claude_on_path(monkeypatch, tmp_path):
    cli = _write_cli(tmp_path / "path-bin")
    monkeypatch.setenv("PATH", str(cli.parent))

    assert (await ClaudeCliLocator().locate("  ")).executable == str(cli)


@pytest.mark.asyncio
async def test_discovers_known_install_locations(monkeypatch, tmp_path):
    cli = _write_cli(tmp_path / "home" / ".local" / "bin")
    monkeypatch.setattr(claude_cli_locator, "_known_paths", lambda: [cli])

    assert (await ClaudeCliLocator().locate()).executable == str(cli)


@pytest.mark.asyncio
async def test_missing_installation_is_not_found():
    with pytest.raises(ClaudeCliNotFound):
        await ClaudeCliLocator().locate()


@pytest.mark.parametrize(
    "build",
    [
        lambda tmp: "relative/claude",
        lambda tmp: str(_write_cli(tmp / "other", name="node")),
        lambda tmp: str(tmp / "missing" / "claude"),
        lambda tmp: str(tmp),
    ],
)
@pytest.mark.asyncio
async def test_explicit_path_must_be_a_claude_executable(tmp_path, build):
    with pytest.raises(ClaudeCliNotFound):
        await ClaudeCliLocator().locate(build(tmp_path))


@pytest.mark.asyncio
async def test_non_executable_file_is_rejected(tmp_path):
    cli = _write_cli(tmp_path / "bin")
    cli.chmod(0o644)

    with pytest.raises(ClaudeCliNotFound):
        await ClaudeCliLocator().locate(str(cli))


@pytest.mark.asyncio
async def test_outdated_version_is_reported(tmp_path):
    cli = _write_cli(tmp_path / "bin", output="2.1.292 (Claude Code)")

    with pytest.raises(ClaudeCliOutdated) as error:
        await ClaudeCliLocator().locate(str(cli))

    assert error.value.version == "2.1.292"


@pytest.mark.parametrize(
    "output, exit_code",
    [("not a version", 0), ("2.1.300 (Claude Code)", 1)],
)
@pytest.mark.asyncio
async def test_unusable_version_output_is_not_found(tmp_path, output, exit_code):
    cli = _write_cli(tmp_path / "bin", output=output, exit_code=exit_code)

    with pytest.raises(ClaudeCliNotFound):
        await ClaudeCliLocator().locate(str(cli))


@pytest.mark.asyncio
async def test_version_check_is_cached_until_invalidated_or_updated(tmp_path):
    cli = _write_cli(tmp_path / "bin")
    locator = ClaudeCliLocator()

    await locator.locate(str(cli))
    await locator.locate(str(cli))
    assert len(_calls(tmp_path / "bin")) == 1

    locator.invalidate()
    await locator.locate(str(cli))
    assert len(_calls(tmp_path / "bin")) == 2

    stat = cli.stat()
    os.utime(cli, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    await locator.locate(str(cli))
    assert len(_calls(tmp_path / "bin")) == 3


@pytest.mark.asyncio
async def test_cli_runs_with_the_user_login_but_without_api_keys(monkeypatch, tmp_path):
    cli = _write_cli(tmp_path / "bin")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-leak")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://proxy.example")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/Users/me/.claude-work")
    monkeypatch.setenv("HOME", "/Users/me")

    await ClaudeCliLocator().locate(str(cli))

    env = (tmp_path / "bin" / "env.log").read_text().splitlines()
    assert not any("sk-ant-leak" in line for line in env)
    assert not any(line.startswith("ANTHROPIC_BASE_URL=") for line in env)
    assert not any(line.startswith("CLAUDECODE=") for line in env)
    assert "CLAUDE_CONFIG_DIR=/Users/me/.claude-work" in env
    assert "HOME=/Users/me" in env
    assert "DISABLE_AUTOUPDATER=1" in env


def _write_auth_cli(directory: Path, status: str, exit_code: int) -> ClaudeCli:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "claude"
    calls = directory / "calls.log"
    path.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> "{calls}"\n'
        f"printf '%s\\n' '{status}'\n"
        f"exit {exit_code}\n"
    )
    path.chmod(0o755)
    return ClaudeCli(executable=str(path), version="2.1.300")


@pytest.mark.parametrize(
    "status, exit_code, expected",
    [
        ('{"loggedIn": true, "authMethod": "claude.ai"}', 0, True),
        ('{"loggedIn": true, "authMethod": "oauth_token"}', 0, True),
        ("Logged in", 0, True),
        ('{"loggedIn": false, "authMethod": "none"}', 1, False),
        ('{"authMethod": "none"}', 0, False),
        ('{"loggedIn": false}', 0, False),
        ("", 1, False),
    ],
)
@pytest.mark.asyncio
async def test_signed_in_reads_auth_status(tmp_path, status, exit_code, expected):
    cli = _write_auth_cli(tmp_path / "bin", status, exit_code)

    assert await ClaudeCliLocator().signed_in(cli) is expected
    assert _calls(tmp_path / "bin") == ["auth status"]


@pytest.mark.asyncio
async def test_signed_in_on_missing_executable_is_not_found(tmp_path):
    with pytest.raises(ClaudeCliNotFound):
        await ClaudeCliLocator().signed_in(
            ClaudeCli(executable=str(tmp_path / "gone" / "claude"), version="2.1.300")
        )
