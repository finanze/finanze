import asyncio
import os
import sys
from pathlib import Path

import pytest
from domain.exception.exceptions import LocalModelError, LocalModelErrorCode
from domain.local_model import (
    LocalModelState,
    LocalRouterModel,
    LocalRuntimeMode,
    LocalRuntimeSource,
)
from infrastructure.local_models import llama_router_process
from infrastructure.local_models.llama_router_process import (
    CACHE_FOLDER,
    LOG_FILE,
    PID_FILE,
    LlamaRouterProcess,
)
from infrastructure.local_models.local_model_imports import presets_path


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakePopen:
    def __init__(self, pid: int, exit_code=None):
        self.pid = pid
        self.returncode = exit_code

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class FakeSpawner:
    def __init__(self, exit_code=None):
        self.exit_code = exit_code
        self.calls: list[tuple[list[str], dict, Path]] = []
        self.processes: list[FakePopen] = []

    def __call__(self, args, env, log_path):
        self.calls.append((args, env, log_path))
        process = FakePopen(4242 + len(self.processes), self.exit_code)
        self.processes.append(process)
        return process


class FakeRouter:
    def __init__(self, healthy=True, models=None):
        self.healthy = healthy
        self.models = models or []
        self.health_checks = 0
        self.list_calls = 0

    async def is_healthy(self, connection):
        self.health_checks += 1
        return self.healthy

    async def list_models(self, connection, reload=False):
        self.list_calls += 1
        return self.models


@pytest.fixture
def killed(monkeypatch):
    calls = []

    def fake_kill(pid, force=False):
        calls.append((pid, force))

    monkeypatch.setattr(llama_router_process, "_kill_tree", fake_kill)
    monkeypatch.setattr(llama_router_process, "_process_name", lambda pid: None)
    return calls


@pytest.fixture
def executable(tmp_path) -> Path:
    path = tmp_path / "bin" / "finanze-llama-server"
    path.parent.mkdir()
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


def _process(executable, tmp_path, router=None, spawner=None, clock=None):
    process = LlamaRouterProcess(
        executable,
        tmp_path / "models",
        router or FakeRouter(),
        clock=clock or Clock(),
        spawn=spawner or FakeSpawner(),
    )
    process.HEALTH_POLL_SECONDS = 0
    process.WATCHDOG_INTERVAL_SECONDS = 0
    return process


def _arg(args: list[str], name: str) -> str:
    return args[args.index(name) + 1]


class TestAvailability:
    def test_missing_executable(self, tmp_path):
        assert not LlamaRouterProcess(None, tmp_path, FakeRouter()).available
        assert not LlamaRouterProcess(
            tmp_path / "missing", tmp_path, FakeRouter()
        ).available

    def test_not_executable(self, tmp_path):
        path = tmp_path / "llama-server"
        path.write_text("x")
        path.chmod(0o644)
        assert not LlamaRouterProcess(path, tmp_path, FakeRouter()).available

    def test_executable(self, executable, tmp_path):
        assert LlamaRouterProcess(executable, tmp_path, FakeRouter()).available

    @pytest.mark.asyncio
    async def test_start_unavailable(self, tmp_path):
        process = LlamaRouterProcess(None, tmp_path, FakeRouter())
        with pytest.raises(LocalModelError) as error:
            await process.ensure_started()
        assert error.value.code == LocalModelErrorCode.RUNTIME_FAILED


class TestStart:
    @pytest.mark.asyncio
    async def test_spawns_router(self, executable, tmp_path, killed):
        spawner = FakeSpawner()
        process = _process(executable, tmp_path, spawner=spawner)
        models_dir = tmp_path / "models"

        connection = await process.ensure_started()

        assert len(spawner.calls) == 1
        args, env, log_path = spawner.calls[0]
        assert args[0] == str(executable)
        assert _arg(args, "--host") == "127.0.0.1"
        port = _arg(args, "--port")
        assert _arg(args, "--models-preset") == str(presets_path(models_dir))
        assert _arg(args, "--models-max") == "1"
        assert _arg(args, "--sleep-idle-seconds") == "600"
        assert _arg(args, "-c") == "8192"
        assert _arg(args, "-np") == "1"
        assert _arg(args, "--reasoning-budget") == "0"
        assert "--no-ui" in args
        assert env["LLAMA_API_KEY"] == connection.api_key
        assert len(connection.api_key) >= 32
        assert env["LLAMA_CACHE"] == str(models_dir / CACHE_FOLDER)
        assert log_path == models_dir / LOG_FILE

        assert connection.base_url == f"http://127.0.0.1:{port}"
        assert connection.mode == LocalRuntimeMode.BUILT_IN
        assert connection.source == LocalRuntimeSource.BUILT_IN
        assert presets_path(models_dir).read_text() == "version = 1\n"
        assert (models_dir / CACHE_FOLDER).is_dir()
        assert (models_dir / PID_FILE).read_text() == "4242"

        await process.stop()

    @pytest.mark.asyncio
    async def test_reuses_running_router(self, executable, tmp_path, killed):
        spawner = FakeSpawner()
        process = _process(executable, tmp_path, spawner=spawner)
        first = await process.ensure_started()
        second = await process.ensure_started()
        assert first is second
        assert len(spawner.calls) == 1
        await process.stop()

    @pytest.mark.asyncio
    async def test_restarts_dead_router(self, executable, tmp_path, killed):
        spawner = FakeSpawner()
        process = _process(executable, tmp_path, spawner=spawner)
        first = await process.ensure_started()
        spawner.processes[0].returncode = 1
        second = await process.ensure_started()
        assert len(spawner.calls) == 2
        assert first.api_key != second.api_key
        await process.stop()

    @pytest.mark.asyncio
    async def test_process_exits_during_startup(self, executable, tmp_path, killed):
        process = _process(executable, tmp_path, spawner=FakeSpawner(exit_code=1))
        with pytest.raises(LocalModelError) as error:
            await process.ensure_started()
        assert error.value.code == LocalModelErrorCode.RUNTIME_FAILED
        assert "code 1" in error.value.details
        assert not (tmp_path / "models" / PID_FILE).exists()

    @pytest.mark.asyncio
    async def test_health_timeout(self, executable, tmp_path, killed):
        clock = Clock()

        class SlowRouter(FakeRouter):
            async def is_healthy(self, connection):
                clock.now += 30
                return False

        process = _process(executable, tmp_path, router=SlowRouter(), clock=clock)
        with pytest.raises(LocalModelError) as error:
            await process.ensure_started()
        assert error.value.code == LocalModelErrorCode.RUNTIME_FAILED
        assert killed == [(4242, False)]
        assert not (tmp_path / "models" / PID_FILE).exists()

    @pytest.mark.asyncio
    async def test_spawn_error(self, executable, tmp_path, killed):
        def failing_spawn(args, env, log_path):
            raise PermissionError("denied")

        process = _process(executable, tmp_path, spawner=failing_spawn)
        with pytest.raises(LocalModelError) as error:
            await process.ensure_started()
        assert error.value.code == LocalModelErrorCode.RUNTIME_FAILED


class TestStaleCleanup:
    @pytest.mark.asyncio
    async def test_kills_stale_router(self, executable, tmp_path, killed, monkeypatch):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / PID_FILE).write_text("999")
        process_name = executable.name
        if sys.platform.startswith("linux"):
            process_name = process_name[: llama_router_process.LINUX_COMM_LENGTH]
        monkeypatch.setattr(
            llama_router_process, "_process_name", lambda pid: process_name
        )
        process = _process(executable, tmp_path)
        await process.ensure_started()
        assert killed == [(999, True)]
        await process.stop()

    @pytest.mark.asyncio
    async def test_ignores_unrelated_process(
        self, executable, tmp_path, killed, monkeypatch
    ):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / PID_FILE).write_text("999")
        monkeypatch.setattr(llama_router_process, "_process_name", lambda pid: "bash")
        process = _process(executable, tmp_path)
        await process.ensure_started()
        assert killed == []
        assert (models_dir / PID_FILE).read_text() == "4242"
        await process.stop()


class TestStop:
    @pytest.mark.asyncio
    async def test_stop_kills_router(self, executable, tmp_path, killed):
        spawner = FakeSpawner()
        process = _process(executable, tmp_path, spawner=spawner)
        await process.ensure_started()
        watchdog = process._watchdog
        await process.stop()
        assert killed == [(4242, False)]
        assert spawner.processes[0].returncode == 0
        assert not (tmp_path / "models" / PID_FILE).exists()
        await asyncio.gather(watchdog, return_exceptions=True)
        assert watchdog.done()

    @pytest.mark.asyncio
    async def test_stop_without_router(self, executable, tmp_path, killed):
        await _process(executable, tmp_path).stop()
        assert killed == []


class TestWatchdog:
    @pytest.mark.asyncio
    async def test_stops_idle_router(self, executable, tmp_path, killed):
        clock = Clock()
        process = _process(executable, tmp_path, clock=clock)
        await process.ensure_started()
        watchdog = process._watchdog
        clock.now += process.IDLE_STOP_SECONDS + 1
        await asyncio.wait_for(watchdog, timeout=2)
        assert killed == [(4242, False)]
        assert process._connection is None

    @pytest.mark.asyncio
    async def test_keeps_busy_router(self, executable, tmp_path, killed):
        clock = Clock()
        router = FakeRouter(
            models=[LocalRouterModel(id="a:Q4", state=LocalModelState.DOWNLOADING)]
        )
        process = _process(executable, tmp_path, router=router, clock=clock)
        await process.ensure_started()
        clock.now += process.IDLE_STOP_SECONDS + 1
        for _ in range(20):
            await asyncio.sleep(0)
        assert router.list_calls >= 1
        assert killed == []
        assert process._connection is not None
        await process.stop()

    @pytest.mark.asyncio
    async def test_recent_use_keeps_router(self, executable, tmp_path, killed):
        clock = Clock()
        router = FakeRouter()
        process = _process(executable, tmp_path, router=router, clock=clock)
        await process.ensure_started()
        clock.now += process.IDLE_STOP_SECONDS - 1
        for _ in range(20):
            await asyncio.sleep(0)
        assert router.list_calls == 0
        assert killed == []
        await process.stop()

    @pytest.mark.asyncio
    async def test_cleans_up_crashed_router(self, executable, tmp_path, killed):
        spawner = FakeSpawner()
        process = _process(executable, tmp_path, spawner=spawner)
        await process.ensure_started()
        watchdog = process._watchdog
        spawner.processes[0].returncode = -9
        await asyncio.wait_for(watchdog, timeout=2)
        assert process._connection is None
        assert killed == []
        assert not (tmp_path / "models" / PID_FILE).exists()


def test_matches_executable_names(monkeypatch):
    monkeypatch.setattr(llama_router_process, "IS_WINDOWS", False)
    monkeypatch.setattr(llama_router_process.sys, "platform", "darwin")
    executable = Path("/app/finanze-llama-server")
    assert llama_router_process._matches_executable("finanze-llama-server", executable)
    assert not llama_router_process._matches_executable("bash", executable)
    assert not llama_router_process._matches_executable(None, executable)

    monkeypatch.setattr(llama_router_process.sys, "platform", "linux")
    assert llama_router_process._matches_executable("finanze-llama-s", executable)

    monkeypatch.setattr(llama_router_process, "IS_WINDOWS", True)
    assert llama_router_process._matches_executable(
        "FINANZE-LLAMA-SERVER.EXE", Path("C:/app/finanze-llama-server.exe")
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX process name lookup")
def test_process_name_lookup():
    assert llama_router_process._process_name(os.getpid())
    assert llama_router_process._process_name(99999999) is None
