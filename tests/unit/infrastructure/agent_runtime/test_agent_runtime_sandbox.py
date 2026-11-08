import stat
from pathlib import Path

import pytest
from infrastructure.agent_runtime.runtime_sandbox import AgentRuntimeSandbox


def _mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_runtime_dir_is_private(tmp_path):
    runtime_dir = AgentRuntimeSandbox(tmp_path / "agents").runtime_dir("copilot")

    assert runtime_dir == tmp_path / "agents" / "copilot" / "runtime"
    assert runtime_dir.is_dir()
    assert _mode(runtime_dir) == 0o700


@pytest.mark.asyncio
async def test_relative_root_yields_absolute_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sandbox = AgentRuntimeSandbox(Path(".storage") / "agents")

    runtime_dir = sandbox.runtime_dir("copilot")
    instance = await sandbox.create_instance("copilot")

    assert runtime_dir == tmp_path / ".storage" / "agents" / "copilot" / "runtime"
    for path in (runtime_dir, instance.root, instance.home, instance.work):
        assert path.is_absolute()


@pytest.mark.asyncio
async def test_instances_are_isolated_private_and_removable(tmp_path):
    sandbox = AgentRuntimeSandbox(tmp_path)

    first = await sandbox.create_instance("copilot")
    second = await sandbox.create_instance("copilot")

    assert first.root != second.root
    assert first.root.parent == tmp_path / "copilot" / "instances"
    for path in (first.root, first.home, first.work):
        assert path.is_dir()
        assert _mode(path) == 0o700

    await first.remove()

    assert not first.root.exists()
    assert second.root.exists()


@pytest.mark.asyncio
async def test_cleanup_stale_keeps_runtime_binaries(tmp_path):
    sandbox = AgentRuntimeSandbox(tmp_path)
    runtime_dir = sandbox.runtime_dir("copilot")
    (runtime_dir / "binary").write_text("runtime")
    instance = await sandbox.create_instance("copilot")
    (instance.home / "session.json").write_text("{}")

    await sandbox.cleanup_stale()

    assert not (tmp_path / "copilot" / "instances").exists()
    assert (runtime_dir / "binary").exists()


@pytest.mark.asyncio
async def test_cleanup_stale_without_root_is_noop(tmp_path):
    await AgentRuntimeSandbox(tmp_path / "missing").cleanup_stale()
    assert not (tmp_path / "missing").exists()
