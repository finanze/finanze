from pathlib import Path

import pytest
from domain.exception.exceptions import LocalModelError, LocalModelErrorCode
from domain.local_model import (
    LocalRouterConnection,
    LocalRuntimeMode,
    LocalRuntimeSource,
)
from infrastructure.local_models import local_model_runtime
from infrastructure.local_models.local_model_runtime import LocalModelRuntimeAdapter

BUILT_IN = LocalRouterConnection(
    base_url="http://127.0.0.1:5000",
    api_key="generated",
    mode=LocalRuntimeMode.BUILT_IN,
    source=LocalRuntimeSource.BUILT_IN,
)


class FakeProcess:
    def __init__(self, models_dir: Path, available: bool = True):
        self.available = available
        self.models_dir = models_dir
        self.started = 0
        self.stopped = 0

    async def ensure_started(self):
        self.started += 1
        return BUILT_IN

    async def stop(self):
        self.stopped += 1


class TestResolve:
    @pytest.mark.asyncio
    async def test_payload_url_wins(self, tmp_path):
        process = FakeProcess(tmp_path)
        runtime = LocalModelRuntimeAdapter(process, "http://env:8080", "env-key")
        connection = await runtime.resolve(
            {"server_url": " http://payload:8080/v1/ ", "api_key": " key "}
        )
        assert connection.base_url == "http://payload:8080"
        assert connection.api_key == "key"
        assert connection.mode == LocalRuntimeMode.EXTERNAL
        assert connection.source == LocalRuntimeSource.PAYLOAD
        assert process.started == 0

    @pytest.mark.asyncio
    async def test_payload_url_never_uses_env_key(self, tmp_path):
        runtime = LocalModelRuntimeAdapter(None, "http://env:8080", "env-key")
        connection = await runtime.resolve({"server_url": "http://payload:8080"})
        assert connection.api_key is None

    @pytest.mark.asyncio
    async def test_environment_url(self, tmp_path):
        process = FakeProcess(tmp_path)
        runtime = LocalModelRuntimeAdapter(process, " http://env:8080 ", "env-key")
        connection = await runtime.resolve({})
        assert connection.base_url == "http://env:8080"
        assert connection.api_key == "env-key"
        assert connection.source == LocalRuntimeSource.ENVIRONMENT
        assert process.started == 0

    @pytest.mark.asyncio
    async def test_payload_key_overrides_env_key(self):
        runtime = LocalModelRuntimeAdapter(None, "http://env:8080", "env-key")
        connection = await runtime.resolve({"server_url": "", "api_key": "mine"})
        assert connection.source == LocalRuntimeSource.ENVIRONMENT
        assert connection.api_key == "mine"

    @pytest.mark.asyncio
    async def test_built_in(self, tmp_path):
        process = FakeProcess(tmp_path)
        runtime = LocalModelRuntimeAdapter(process, "  ", None)
        assert await runtime.resolve(None) == BUILT_IN
        assert process.started == 1

    @pytest.mark.asyncio
    async def test_missing_server(self, tmp_path):
        runtime = LocalModelRuntimeAdapter(FakeProcess(tmp_path, available=False))
        with pytest.raises(LocalModelError) as error:
            await runtime.resolve({})
        assert error.value.code == LocalModelErrorCode.MISSING_SERVER_URL

    @pytest.mark.parametrize("url", ["localhost:8080", "ftp://host", "http://h/?a=1"])
    @pytest.mark.asyncio
    async def test_invalid_url(self, url):
        runtime = LocalModelRuntimeAdapter(None)
        with pytest.raises(LocalModelError) as error:
            await runtime.resolve({"server_url": url})
        assert error.value.code == LocalModelErrorCode.INVALID_URL

    @pytest.mark.asyncio
    async def test_invalid_env_url(self):
        runtime = LocalModelRuntimeAdapter(None, "not a url")
        with pytest.raises(LocalModelError) as error:
            await runtime.resolve({})
        assert error.value.code == LocalModelErrorCode.INVALID_URL


class TestCapabilities:
    def test_built_in(self, tmp_path, monkeypatch):
        monkeypatch.setattr(local_model_runtime, "system_memory", lambda: 16_000)
        capabilities = LocalModelRuntimeAdapter(FakeProcess(tmp_path)).capabilities()
        assert capabilities.built_in_available is True
        assert capabilities.can_import_files is True
        assert capabilities.env_server_url is None
        assert capabilities.env_api_key_set is False
        assert capabilities.system_memory == 16_000

    def test_server_only(self, monkeypatch):
        monkeypatch.setattr(local_model_runtime, "system_memory", lambda: 16_000)
        capabilities = LocalModelRuntimeAdapter(
            None, "http://env:8080", "key"
        ).capabilities()
        assert capabilities.built_in_available is False
        assert capabilities.can_import_files is False
        assert capabilities.env_server_url == "http://env:8080"
        assert capabilities.env_api_key_set is True
        assert capabilities.system_memory is None


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_stop(self, tmp_path):
        process = FakeProcess(tmp_path)
        await LocalModelRuntimeAdapter(process).stop()
        assert process.stopped == 1

    @pytest.mark.asyncio
    async def test_stop_without_process(self):
        await LocalModelRuntimeAdapter(None).stop()

    def test_free_space(self, tmp_path):
        process = FakeProcess(tmp_path / "models")
        free = LocalModelRuntimeAdapter(process).free_space()
        assert free is not None and free > 0
        assert (tmp_path / "models").is_dir()

    def test_free_space_without_built_in(self, tmp_path):
        process = FakeProcess(tmp_path, available=False)
        assert LocalModelRuntimeAdapter(process).free_space() is None


def test_system_memory():
    memory = local_model_runtime.system_memory()
    assert memory is None or memory > 0
