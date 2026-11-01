import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

FINANZE_DIR = Path(__file__).parents[2] / "finanze"
CLEANUP_MARKER = "cleanup done"
STARTUP_TIMEOUT_SECONDS = 60
SHUTDOWN_TIMEOUT_SECONDS = 30

SCRIPT = f"""
import asyncio
import sys

import uvicorn

from server import serve


async def app(scope, receive, send):
    await send({{"type": "http.response.start", "status": 204, "headers": []}})
    await send({{"type": "http.response.body", "body": b""}})


async def main(port):
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, lifespan="off", log_config=None
    )
    try:
        await serve(uvicorn.Server(config))
    finally:
        print("{CLEANUP_MARKER}", flush=True)


asyncio.run(main(int(sys.argv[1])))
"""


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_listening(process: subprocess.Popen, port: int):
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"Server exited early: {process.stderr.read()}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    pytest.fail("Server did not start listening")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_sigterm_runs_cleanup_after_serve():
    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, "-c", SCRIPT, str(port)],
        cwd=FINANZE_DIR,
        env={**os.environ, "PYTHONPATH": str(FINANZE_DIR)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_listening(process, port)
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=SHUTDOWN_TIMEOUT_SECONDS)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == 0, stderr
    assert CLEANUP_MARKER in stdout
