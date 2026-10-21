import asyncio
import logging
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from application.ports.local_model_router import LocalModelRouter
from domain.exception.exceptions import LocalModelError, LocalModelErrorCode
from domain.local_model import (
    LocalModelState,
    LocalRouterConnection,
    LocalRuntimeMode,
    LocalRuntimeSource,
)
from infrastructure.local_models.local_model_imports import (
    ensure_presets,
    presets_path,
)

HOST = "127.0.0.1"
LOG_FILE = "llama-server.log"
PID_FILE = "llama-server.pid"
CACHE_FOLDER = "cache"
LINUX_COMM_LENGTH = 15
BUSY_STATES = {LocalModelState.DOWNLOADING, LocalModelState.LOADING}
IS_WINDOWS = sys.platform == "win32"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _spawn(args: list[str], env: dict, log_path: Path) -> subprocess.Popen:
    with open(log_path, "wb") as log:
        kwargs = {
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": log,
            "stderr": subprocess.STDOUT,
        }
        if IS_WINDOWS:
            kwargs["creationflags"] = (
                CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            kwargs["start_new_session"] = True
        return subprocess.Popen(args, **kwargs)


def _process_name(pid: int) -> Optional[str]:
    try:
        if IS_WINDOWS:
            output = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW,
            ).stdout
            if not output.startswith('"'):
                return None
            return output.split(",")[0].strip('"')
        if sys.platform.startswith("linux"):
            return Path(f"/proc/{pid}/comm").read_text().strip()
        output = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        return Path(output).name if output else None
    except (OSError, subprocess.SubprocessError):
        return None


def _matches_executable(name: Optional[str], executable: Path) -> bool:
    if not name:
        return False
    expected = executable.name
    if IS_WINDOWS:
        return name.casefold() == expected.casefold()
    if sys.platform.startswith("linux"):
        return name == expected[:LINUX_COMM_LENGTH]
    return name == expected


def _kill_tree(pid: int, force: bool = False):
    if IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            timeout=15,
            creationflags=CREATE_NO_WINDOW,
        )
        return
    os.killpg(pid, signal.SIGKILL if force else signal.SIGTERM)


class LlamaRouterProcess:
    HEALTH_TIMEOUT_SECONDS = 60.0
    HEALTH_POLL_SECONDS = 0.5
    STOP_TIMEOUT_SECONDS = 10.0
    IDLE_STOP_SECONDS = 900.0
    WATCHDOG_INTERVAL_SECONDS = 30.0
    MODEL_SLEEP_SECONDS = 600
    CONTEXT_SIZE = 8192

    def __init__(
        self,
        executable: Optional[Path],
        models_dir: Path,
        router: LocalModelRouter,
        clock: Callable[[], float] = time.monotonic,
        spawn: Callable[[list[str], dict, Path], subprocess.Popen] = _spawn,
    ):
        self._executable = executable
        self._models_dir = models_dir
        self._router = router
        self._clock = clock
        self._spawn = spawn
        self._lock = asyncio.Lock()
        self._process: Optional[subprocess.Popen] = None
        self._connection: Optional[LocalRouterConnection] = None
        self._last_used = 0.0
        self._watchdog: Optional[asyncio.Task] = None
        self._log = logging.getLogger(__name__)

    @property
    def available(self) -> bool:
        return (
            self._executable is not None
            and self._executable.is_file()
            and os.access(self._executable, os.X_OK)
        )

    @property
    def models_dir(self) -> Path:
        return self._models_dir

    def touch(self):
        self._last_used = self._clock()

    async def ensure_started(self) -> LocalRouterConnection:
        if not self.available:
            raise LocalModelError(
                LocalModelErrorCode.RUNTIME_FAILED, "Built-in engine not available"
            )
        async with self._lock:
            if self._connection is not None and self._alive():
                self.touch()
                return self._connection
            await self._stop_locked()
            return await self._start_locked()

    async def stop(self):
        async with self._lock:
            await self._stop_locked()

    def _alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    async def _start_locked(self) -> LocalRouterConnection:
        self._models_dir.mkdir(parents=True, exist_ok=True)
        cache_dir = self._models_dir / CACHE_FOLDER
        cache_dir.mkdir(parents=True, exist_ok=True)
        ensure_presets(self._models_dir)
        await asyncio.to_thread(self._cleanup_stale)

        port = _free_port()
        api_key = secrets.token_urlsafe(32)
        env = {
            **os.environ,
            "LLAMA_API_KEY": api_key,
            "LLAMA_CACHE": str(cache_dir),
        }
        args = [
            str(self._executable),
            "--host",
            HOST,
            "--port",
            str(port),
            "--models-preset",
            str(presets_path(self._models_dir)),
            "--models-max",
            "1",
            "--sleep-idle-seconds",
            str(self.MODEL_SLEEP_SECONDS),
            "-c",
            str(self.CONTEXT_SIZE),
            "-np",
            "1",
            "--no-ui",
            "--reasoning-budget",
            "0",
        ]
        self._log.info(f"Starting built-in llama.cpp server on port {port}")
        try:
            process = self._spawn(args, env, self._models_dir / LOG_FILE)
        except OSError as e:
            raise LocalModelError(LocalModelErrorCode.RUNTIME_FAILED, str(e)) from e
        self._process = process
        self._write_pid(process.pid)

        connection = LocalRouterConnection(
            base_url=f"http://{HOST}:{port}",
            api_key=api_key,
            mode=LocalRuntimeMode.BUILT_IN,
            source=LocalRuntimeSource.BUILT_IN,
        )
        await self._wait_healthy(connection)
        self._connection = connection
        self.touch()
        self._watchdog = asyncio.create_task(self._watch())
        return connection

    async def _wait_healthy(self, connection: LocalRouterConnection):
        deadline = self._clock() + self.HEALTH_TIMEOUT_SECONDS
        while True:
            if not self._alive():
                code = self._process.returncode if self._process else None
                await self._stop_locked()
                raise LocalModelError(
                    LocalModelErrorCode.RUNTIME_FAILED,
                    f"Built-in engine exited with code {code}",
                )
            if await self._router.is_healthy(connection):
                return
            if self._clock() >= deadline:
                await self._stop_locked()
                raise LocalModelError(
                    LocalModelErrorCode.RUNTIME_FAILED,
                    "Built-in engine did not become ready",
                )
            await asyncio.sleep(self.HEALTH_POLL_SECONDS)

    async def _watch(self):
        try:
            while True:
                await asyncio.sleep(self.WATCHDOG_INTERVAL_SECONDS)
                if not self._alive():
                    self._log.warning("Built-in llama.cpp server exited unexpectedly")
                    async with self._lock:
                        self._watchdog = None
                        await self._stop_locked()
                    return
                if self._clock() - self._last_used < self.IDLE_STOP_SECONDS:
                    continue
                if await self._busy():
                    self.touch()
                    continue
                self._log.info("Stopping idle built-in llama.cpp server")
                async with self._lock:
                    self._watchdog = None
                    await self._stop_locked()
                return
        except asyncio.CancelledError:
            pass

    async def _busy(self) -> bool:
        connection = self._connection
        if connection is None:
            return False
        try:
            models = await self._router.list_models(connection)
        except LocalModelError:
            return False
        return any(model.state in BUSY_STATES for model in models)

    async def _stop_locked(self):
        watchdog, self._watchdog = self._watchdog, None
        if watchdog is not None and watchdog is not asyncio.current_task():
            watchdog.cancel()
        process, self._process = self._process, None
        self._connection = None
        if process is None:
            return
        if process.poll() is None:
            await asyncio.to_thread(self._terminate, process)
        self._remove_pid()

    def _terminate(self, process: subprocess.Popen):
        try:
            _kill_tree(process.pid)
            process.wait(timeout=self.STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self._log.warning("Built-in llama.cpp server did not stop, killing it")
            try:
                _kill_tree(process.pid, force=True)
                process.wait(timeout=self.STOP_TIMEOUT_SECONDS)
            except (OSError, subprocess.SubprocessError) as e:
                self._log.error(f"Could not kill built-in llama.cpp server: {e}")
        except (OSError, subprocess.SubprocessError) as e:
            self._log.warning(f"Could not stop built-in llama.cpp server: {e}")

    def _cleanup_stale(self):
        pid_file = self._models_dir / PID_FILE
        try:
            pid = int(pid_file.read_text().strip())
        except (OSError, ValueError):
            return
        if _matches_executable(_process_name(pid), self._executable):
            self._log.info(f"Stopping stale built-in llama.cpp server ({pid})")
            try:
                _kill_tree(pid, force=True)
            except (OSError, subprocess.SubprocessError) as e:
                self._log.warning(f"Could not stop stale llama.cpp server: {e}")
        self._remove_pid()

    def _write_pid(self, pid: int):
        try:
            (self._models_dir / PID_FILE).write_text(str(pid))
        except OSError as e:
            self._log.warning(f"Could not write llama.cpp server pid file: {e}")

    def _remove_pid(self):
        try:
            (self._models_dir / PID_FILE).unlink(missing_ok=True)
        except OSError:
            pass
