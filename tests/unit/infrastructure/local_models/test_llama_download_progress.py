import asyncio
import json

import httpx
import pytest
from domain.local_model import (
    LocalRouterConnection,
    LocalRuntimeMode,
    LocalRuntimeSource,
)
from infrastructure.local_models.llama_download_progress import LlamaDownloadProgress

CONNECTION = LocalRouterConnection(
    base_url="http://127.0.0.1:8080",
    api_key="secret",
    mode=LocalRuntimeMode.BUILT_IN,
    source=LocalRuntimeSource.BUILT_IN,
)


def _event(model: str, event: str, files: dict | None = None) -> str:
    data = {"progress": files} if files is not None else {}
    return json.dumps({"model": model, "event": event, "data": data})


def _sse(*events: str) -> bytes:
    return "".join(f"data: {event}\n\n" for event in events).encode()


class OpenStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes, release: asyncio.Event):
        self._content = content
        self._release = release

    async def __aiter__(self):
        yield self._content
        await self._release.wait()


class FakeServer:
    def __init__(self, content: bytes = b"", status: int = 200, keep_open=False):
        self.content = content
        self.status = status
        self.release = asyncio.Event()
        self.keep_open = keep_open
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.keep_open:
            return httpx.Response(
                self.status, stream=OpenStream(self.content, self.release)
            )
        return httpx.Response(self.status, content=self.content)

    def factory(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


class TestHandle:
    def test_sums_file_progress(self):
        progress = LlamaDownloadProgress()
        done = progress._handle(
            _event(
                "a:Q4",
                "download_progress",
                {
                    "model.gguf": {"done": 100, "total": 300},
                    "mmproj.gguf": {"done": "50", "total": 100},
                },
            )
        )
        assert done is False
        assert progress.get("a:Q4") == (150, 400)

    def test_unknown_total(self):
        progress = LlamaDownloadProgress()
        progress._handle(
            _event(
                "a:Q4",
                "download_progress",
                {"model.gguf": {"done": 100, "total": 300}, "x": {"done": 5}},
            )
        )
        assert progress.get("a:Q4") == (105, None)

    def test_finished_clears_and_stops_when_last(self):
        progress = LlamaDownloadProgress()
        progress._handle(_event("a:Q4", "download_progress", {"f": {"done": 1}}))
        progress._handle(_event("b:Q4", "download_progress", {"f": {"done": 2}}))
        assert progress._handle(_event("a:Q4", "download_finished")) is False
        assert progress.get("a:Q4") is None
        assert progress._handle(_event("b:Q4", "download_failed")) is True
        assert progress.get("b:Q4") is None

    @pytest.mark.parametrize(
        "raw",
        [
            "not json",
            "[]",
            json.dumps({"event": "download_progress"}),
            _event("a:Q4", "model_loaded"),
            _event("a:Q4", "download_progress"),
        ],
    )
    def test_ignores_other_events(self, raw):
        progress = LlamaDownloadProgress()
        assert progress._handle(raw) is False
        assert progress.get("a:Q4") is None


class TestWatch:
    @pytest.mark.asyncio
    async def test_streams_progress_with_auth(self):
        server = FakeServer(
            _sse(
                _event("a:Q4", "download_progress", {"f": {"done": 10, "total": 40}}),
                _event("a:Q4", "download_progress", {"f": {"done": 20, "total": 40}}),
            )
        )
        progress = LlamaDownloadProgress(server.factory)
        progress.watch(CONNECTION, {"a:Q4"})
        await progress._task
        assert progress.get("a:Q4") == (20, 40)
        request = server.requests[0]
        assert str(request.url) == "http://127.0.0.1:8080/models/sse"
        assert request.headers["Authorization"] == "Bearer secret"

    @pytest.mark.asyncio
    async def test_stops_reading_when_all_finished(self):
        server = FakeServer(
            _sse(
                _event("a:Q4", "download_progress", {"f": {"done": 10}}),
                _event("a:Q4", "download_finished"),
            ),
            keep_open=True,
        )
        progress = LlamaDownloadProgress(server.factory)
        progress.watch(CONNECTION, {"a:Q4"})
        await asyncio.wait_for(progress._task, timeout=2)
        assert progress.get("a:Q4") is None

    @pytest.mark.asyncio
    async def test_non_200_stream_is_ignored(self):
        server = FakeServer(status=404)
        progress = LlamaDownloadProgress(server.factory)
        progress.watch(CONNECTION, {"a:Q4"})
        await progress._task
        assert progress.get("a:Q4") is None

    @pytest.mark.asyncio
    async def test_reuses_running_stream_for_same_target(self):
        server = FakeServer(keep_open=True)
        progress = LlamaDownloadProgress(server.factory)
        progress.watch(CONNECTION, {"a:Q4"})
        task = progress._task
        progress.watch(CONNECTION, {"a:Q4", "b:Q4"})
        assert progress._task is task

        other = LocalRouterConnection(
            base_url="http://127.0.0.1:9090",
            mode=LocalRuntimeMode.BUILT_IN,
            source=LocalRuntimeSource.BUILT_IN,
        )
        progress.watch(other, {"a:Q4"})
        assert progress._task is not task
        await asyncio.gather(task, return_exceptions=True)
        assert task.cancelled()
        current = progress._task
        progress.stop()
        await asyncio.gather(current, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_prunes_and_stops_without_downloads(self):
        server = FakeServer(keep_open=True)
        progress = LlamaDownloadProgress(server.factory)
        progress._progress = {"a:Q4": (1, 2), "b:Q4": (3, 4)}
        progress.watch(CONNECTION, {"b:Q4"})
        assert progress.get("a:Q4") is None
        assert progress.get("b:Q4") == (3, 4)
        task = progress._task

        progress.watch(CONNECTION, set())
        assert progress._task is None
        assert progress.get("b:Q4") is None
        await asyncio.gather(task, return_exceptions=True)
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_connection_errors_are_swallowed(self):
        def failing(request):
            raise httpx.ConnectError("refused")

        progress = LlamaDownloadProgress(
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(failing))
        )
        progress.watch(CONNECTION, {"a:Q4"})
        await progress._task
        assert progress._task.exception() is None
