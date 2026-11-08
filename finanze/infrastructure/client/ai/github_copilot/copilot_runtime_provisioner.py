import asyncio
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

import certifi

CLI_PATH_ENV = "COPILOT_CLI_PATH"
EXTRACT_DIR_ENV = "COPILOT_CLI_EXTRACT_DIR"


class CopilotRuntimeUnavailable(Exception):
    pass


class CopilotRuntimeProvisioner:
    def __init__(self, runtime_dir: Path):
        self._runtime_dir = runtime_dir
        self._lock = asyncio.Lock()
        self._executable: Optional[str] = None
        self._prefetch_task: Optional[asyncio.Task] = None
        self._log = logging.getLogger(__name__)

    def prefetch(self):
        if os.environ.get(CLI_PATH_ENV) or self._executable:
            return
        if self._prefetch_task is not None and not self._prefetch_task.done():
            return
        self._prefetch_task = asyncio.create_task(self._prefetch())

    async def ensure(self) -> str:
        override = os.environ.get(CLI_PATH_ENV)
        if override:
            return override
        if self._executable:
            return self._executable
        async with self._lock:
            if not self._executable:
                try:
                    self._executable = await asyncio.to_thread(self._stage)
                except Exception as e:
                    raise CopilotRuntimeUnavailable(str(e)) from e
            return self._executable

    async def _prefetch(self):
        try:
            await self.ensure()
        except CopilotRuntimeUnavailable:
            self._log.warning("Could not prefetch the GitHub Copilot runtime")

    def _stage(self) -> str:
        # Deferred: importing the Copilot SDK adds about a second to startup.
        from copilot import _cli_download, _cli_version

        version = _cli_version.CLI_VERSION
        if not version:
            raise RuntimeError("The Copilot SDK has no pinned runtime version")

        version_dir = self._runtime_dir / re.sub(r"[^a-zA-Z0-9._\-]", "_", version)
        managed = os.environ.get(EXTRACT_DIR_ENV) in (None, str(version_dir))
        if managed:
            os.environ[EXTRACT_DIR_ENV] = str(version_dir)
        if getattr(sys, "frozen", False):
            os.environ.setdefault("SSL_CERT_FILE", certifi.where())

        self._log.info(f"Preparing GitHub Copilot runtime {version}")
        executable = _cli_download.ensure_runtime_wrapper(version)
        if managed:
            self._remove_other_versions(version_dir)
        return executable

    def _remove_other_versions(self, current: Path):
        for entry in self._runtime_dir.iterdir():
            if entry.is_dir() and entry != current:
                shutil.rmtree(entry, ignore_errors=True)
