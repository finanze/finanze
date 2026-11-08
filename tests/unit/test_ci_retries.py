import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import package_llama
import pytest


ROOT = Path(__file__).resolve().parents[2]
RETRY_SCRIPT = ROOT / ".github" / "scripts" / "retry.sh"


@pytest.mark.parametrize(
    ("max_attempts", "success_attempt"),
    [(None, 1), (None, 2), (None, 3), (None, 4), (2, 1), (2, 2), (2, 3)],
)
def test_retry_command(max_attempts, success_attempt, tmp_path):
    calls = tmp_path / "calls"
    sleeps = tmp_path / "sleeps"
    sleep = tmp_path / "sleep"
    sleep.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$1" >> "$SLEEPS"\n')
    sleep.chmod(0o755)
    env = os.environ | {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "CALLS": str(calls),
        "SLEEPS": str(sleeps),
        "SUCCESS_ATTEMPT": str(success_attempt),
    }
    if max_attempts is None:
        env.pop("RETRY_ATTEMPTS", None)
    else:
        env["RETRY_ATTEMPTS"] = str(max_attempts)

    result = subprocess.run(
        [
            "bash",
            str(RETRY_SCRIPT),
            "bash",
            "-c",
            'printf "%s\\n" "$1" >> "$CALLS"; '
            '[ "$(wc -l < "$CALLS")" -ge "$SUCCESS_ATTEMPT" ] || exit 23',
            "_",
            "argument with spaces",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    limit = max_attempts or 3
    expected_attempts = min(success_attempt, limit)
    assert result.returncode == (0 if success_attempt <= limit else 23)
    assert (
        calls.read_text().splitlines() == ["argument with spaces"] * expected_attempts
    )
    actual_sleeps = sleeps.read_text().splitlines() if sleeps.exists() else []
    assert actual_sleeps == ["10", "20"][: expected_attempts - 1]


def test_retry_requires_a_command():
    result = subprocess.run(
        ["bash", str(RETRY_SCRIPT)], capture_output=True, text=True, check=False
    )

    assert result.returncode == 2
    assert "No command provided" in result.stderr


@pytest.mark.parametrize("max_attempts", ["", "0", "-1", "abc", "100"])
def test_retry_rejects_invalid_attempts(max_attempts):
    result = subprocess.run(
        ["bash", str(RETRY_SCRIPT), "true"],
        env=os.environ | {"RETRY_ATTEMPTS": max_attempts},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "RETRY_ATTEMPTS must be" in result.stderr


@pytest.mark.parametrize("noconfirm", [False, True])
def test_package_can_replace_previous_ci_output(monkeypatch, tmp_path, noconfirm):
    commands = []
    backend_output = tmp_path / "backend" / "dist" / "finanze-server"
    release = tmp_path / "frontend" / "app" / "release"
    release.mkdir(parents=True)

    def run_command(command, *, shell, env=None):
        assert shell
        commands.append(command)
        if command.startswith("pyinstaller "):
            if backend_output.exists():
                assert "--noconfirm" in command
            backend_output.mkdir(parents=True, exist_ok=True)
        elif command.startswith("pnpm run dist"):
            (release / "Finanze-test.dmg").write_text(f"build {len(commands)}")
        return 0

    monkeypatch.setattr(subprocess, "call", run_command)
    monkeypatch.setattr(package_llama, "fetch_llama_server", lambda **kwargs: None)
    argv = ["package.py", "--target", "full", "--os", "mac"]
    if noconfirm:
        argv.append("--noconfirm")
    monkeypatch.setattr(sys, "argv", argv)

    for _ in range(2 if noconfirm else 1):
        monkeypatch.chdir(tmp_path)
        runpy.run_path(str(ROOT / "package.py"), run_name="__main__")

    pyinstaller_commands = [cmd for cmd in commands if cmd.startswith("pyinstaller ")]
    assert len(pyinstaller_commands) == (2 if noconfirm else 1)
    assert all(("--noconfirm" in cmd) == noconfirm for cmd in pyinstaller_commands)
    assert (tmp_path / "dist" / "Finanze-test.dmg").read_text() == (
        "build 6" if noconfirm else "build 3"
    )


def test_package_preserves_existing_output_by_default(monkeypatch, tmp_path):
    release = tmp_path / "frontend" / "app" / "release"
    release.mkdir(parents=True)
    (release / "Finanze-test.dmg").write_text("new build")
    dist = tmp_path / "dist"
    dist.mkdir()
    existing = dist / "Finanze-test.dmg"
    existing.write_text("existing build")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["package.py", "--target", "frontend"])
    monkeypatch.setattr(subprocess, "call", lambda *args, **kwargs: 0)

    with pytest.raises(shutil.Error):
        runpy.run_path(str(ROOT / "package.py"), run_name="__main__")

    assert existing.read_text() == "existing build"
