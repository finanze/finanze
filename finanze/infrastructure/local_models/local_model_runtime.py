import ctypes
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from application.ports.local_model_runtime import LocalModelRuntime
from domain.exception.exceptions import LocalModelError, LocalModelErrorCode
from domain.external_integration import ExternalIntegrationPayload
from domain.local_model import (
    LocalModelsCapabilities,
    LocalRouterConnection,
    LocalRuntimeMode,
    LocalRuntimeSource,
)
from infrastructure.client.ai.server_url import server_root_url
from infrastructure.local_models.llama_router_process import LlamaRouterProcess


def system_memory() -> Optional[int]:
    try:
        if sys.platform == "win32":

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            return int(status.ullTotalPhys)
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def _router_url(url: str) -> str:
    try:
        return server_root_url(url)
    except ValueError:
        raise LocalModelError(LocalModelErrorCode.INVALID_URL)


class LocalModelRuntimeAdapter(LocalModelRuntime):
    def __init__(
        self,
        process: Optional[LlamaRouterProcess],
        env_server_url: Optional[str] = None,
        env_api_key: Optional[str] = None,
    ):
        self._process = process
        self._env_server_url = (env_server_url or "").strip() or None
        self._env_api_key = (env_api_key or "").strip() or None
        self._log = logging.getLogger(__name__)

    def _built_in_available(self) -> bool:
        return self._process is not None and self._process.available

    def capabilities(self) -> LocalModelsCapabilities:
        built_in = self._built_in_available()
        return LocalModelsCapabilities(
            built_in_available=built_in,
            can_import_files=built_in,
            env_server_url=self._env_server_url,
            env_api_key_set=self._env_api_key is not None,
            system_memory=system_memory() if built_in else None,
        )

    async def resolve(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> LocalRouterConnection:
        payload = credentials or {}
        server_url = (payload.get("server_url") or "").strip()
        api_key = (payload.get("api_key") or "").strip() or None
        if server_url:
            return LocalRouterConnection(
                base_url=_router_url(server_url),
                api_key=api_key,
                mode=LocalRuntimeMode.EXTERNAL,
                source=LocalRuntimeSource.PAYLOAD,
            )
        if self._env_server_url:
            return LocalRouterConnection(
                base_url=_router_url(self._env_server_url),
                api_key=api_key or self._env_api_key,
                mode=LocalRuntimeMode.EXTERNAL,
                source=LocalRuntimeSource.ENVIRONMENT,
            )
        if self._built_in_available():
            return await self._process.ensure_started()
        raise LocalModelError(LocalModelErrorCode.MISSING_SERVER_URL)

    async def stop(self):
        if self._process is not None:
            await self._process.stop()

    def free_space(self) -> Optional[int]:
        if not self._built_in_available():
            return None
        models_dir: Path = self._process.models_dir
        try:
            models_dir.mkdir(parents=True, exist_ok=True)
            return shutil.disk_usage(models_dir).free
        except OSError as e:
            self._log.warning(f"Could not read free disk space: {e}")
            return None
