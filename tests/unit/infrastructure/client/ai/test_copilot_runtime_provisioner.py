import asyncio
import os

import copilot._cli_download as cli_download
import copilot._cli_version as cli_version
import pytest
from infrastructure.client.ai.github_copilot.copilot_runtime_provisioner import (
    CLI_PATH_ENV,
    EXTRACT_DIR_ENV,
    CopilotRuntimeProvisioner,
    CopilotRuntimeUnavailable,
)

VERSION = "1.0.105"


@pytest.fixture
def clean_env(monkeypatch):
    for name in (CLI_PATH_ENV, EXTRACT_DIR_ENV):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    monkeypatch.setattr(cli_version, "CLI_VERSION", VERSION)
    return monkeypatch


def _fake_download(calls: list):
    def ensure_runtime_wrapper(version):
        extract_dir = os.environ[EXTRACT_DIR_ENV]
        calls.append((version, extract_dir))
        os.makedirs(extract_dir, exist_ok=True)
        return os.path.join(extract_dir, "copilot-runtime")

    return ensure_runtime_wrapper


@pytest.mark.asyncio
async def test_stages_pinned_runtime_once_and_removes_old_versions(clean_env, tmp_path):
    calls = []
    clean_env.setattr(cli_download, "ensure_runtime_wrapper", _fake_download(calls))
    stale = tmp_path / "1.0.90"
    stale.mkdir()
    provisioner = CopilotRuntimeProvisioner(tmp_path)

    paths = await asyncio.gather(*(provisioner.ensure() for _ in range(3)))

    expected_dir = str(tmp_path / VERSION)
    assert calls == [(VERSION, expected_dir)]
    assert set(paths) == {os.path.join(expected_dir, "copilot-runtime")}
    assert not stale.exists()
    assert (tmp_path / VERSION).is_dir()
    assert await provisioner.ensure() == paths[0]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_explicit_runtime_path_skips_staging(clean_env, tmp_path):
    clean_env.setenv(CLI_PATH_ENV, "/opt/copilot/runtime")
    clean_env.setattr(
        cli_download,
        "ensure_runtime_wrapper",
        lambda version: pytest.fail("runtime should not be downloaded"),
    )
    provisioner = CopilotRuntimeProvisioner(tmp_path)

    provisioner.prefetch()

    assert await provisioner.ensure() == "/opt/copilot/runtime"


@pytest.mark.asyncio
async def test_user_extract_dir_is_respected(clean_env, tmp_path):
    calls = []
    custom = tmp_path / "custom"
    clean_env.setenv(EXTRACT_DIR_ENV, str(custom))
    clean_env.setattr(cli_download, "ensure_runtime_wrapper", _fake_download(calls))
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    kept = runtime_dir / "other"
    kept.mkdir()

    await CopilotRuntimeProvisioner(runtime_dir).ensure()

    assert calls == [(VERSION, str(custom))]
    assert kept.exists()


@pytest.mark.asyncio
async def test_failures_are_reported_and_retried(clean_env, tmp_path):
    attempts = []

    def failing(version):
        attempts.append(version)
        raise OSError("offline")

    clean_env.setattr(cli_download, "ensure_runtime_wrapper", failing)
    provisioner = CopilotRuntimeProvisioner(tmp_path)

    with pytest.raises(CopilotRuntimeUnavailable):
        await provisioner.ensure()

    calls = []
    clean_env.setattr(cli_download, "ensure_runtime_wrapper", _fake_download(calls))
    assert await provisioner.ensure()
    assert len(attempts) == 1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_prefetch_swallows_failures(clean_env, tmp_path):
    def failing(version):
        raise OSError("offline")

    clean_env.setattr(cli_download, "ensure_runtime_wrapper", failing)
    provisioner = CopilotRuntimeProvisioner(tmp_path)

    provisioner.prefetch()
    provisioner.prefetch()
    await provisioner._prefetch_task

    assert provisioner._prefetch_task.exception() is None
