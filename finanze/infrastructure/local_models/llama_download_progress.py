import asyncio
import json
import logging
from typing import Callable, Optional

import httpx
from domain.local_model import LocalRouterConnection

PROGRESS_EVENT = "download_progress"
FINISHED_EVENTS = {"download_finished", "download_failed"}


def _default_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None))


def _int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class LlamaDownloadProgress:
    def __init__(
        self, client_factory: Callable[[], httpx.AsyncClient] = _default_client
    ):
        self._client_factory = client_factory
        self._progress: dict[str, tuple[int, Optional[int]]] = {}
        self._task: Optional[asyncio.Task] = None
        self._target: Optional[tuple[str, Optional[str]]] = None
        self._log = logging.getLogger(__name__)

    def get(self, model_id: str) -> Optional[tuple[int, Optional[int]]]:
        return self._progress.get(model_id)

    def watch(self, connection: LocalRouterConnection, downloading: set[str]):
        for model_id in list(self._progress):
            if model_id not in downloading:
                del self._progress[model_id]
        if not downloading:
            self.stop()
            return
        target = (connection.base_url, connection.api_key)
        if self._task is not None and not self._task.done() and self._target == target:
            return
        self.stop()
        self._target = target
        self._task = asyncio.create_task(self._listen(connection))

    def stop(self):
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
        self._target = None

    async def _listen(self, connection: LocalRouterConnection):
        headers = (
            {"Authorization": f"Bearer {connection.api_key}"}
            if connection.api_key
            else {}
        )
        try:
            async with self._client_factory() as client:
                async with client.stream(
                    "GET", f"{connection.base_url}/models/sse", headers=headers
                ) as response:
                    if response.status_code != 200:
                        return
                    async for line in response.aiter_lines():
                        if line.startswith("data:") and self._handle(line[5:]):
                            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._log.debug(f"Download progress stream closed: {type(e).__name__}")

    def _handle(self, raw: str) -> bool:
        try:
            event = json.loads(raw)
        except ValueError:
            return False
        if not isinstance(event, dict) or not isinstance(event.get("model"), str):
            return False
        model_id = event["model"]
        name = event.get("event")
        if name in FINISHED_EVENTS:
            self._progress.pop(model_id, None)
            return not self._progress
        if name != PROGRESS_EVENT:
            return False
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        progress = data.get("progress")
        if not isinstance(progress, dict):
            return False
        files = [item for item in progress.values() if isinstance(item, dict)]
        done = sum(_int(item.get("done")) or 0 for item in files)
        totals = [_int(item.get("total")) for item in files]
        total = sum(totals) if totals and all(totals) else None
        self._progress[model_id] = (done, total)
        return False
