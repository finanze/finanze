import asyncio
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

RUNTIME_DIR = "runtime"
INSTANCES_DIR = "instances"


def _ensure_private_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


@dataclass(frozen=True)
class AgentRuntimeInstanceDirs:
    root: Path
    home: Path
    work: Path

    async def remove(self):
        await asyncio.to_thread(shutil.rmtree, self.root, True)


class AgentRuntimeSandbox:
    def __init__(self, root: Path):
        self._root = root

    def runtime_dir(self, provider: str) -> Path:
        path = self._root / provider / RUNTIME_DIR
        _ensure_private_dir(path)
        return path

    async def create_instance(self, provider: str) -> AgentRuntimeInstanceDirs:
        return await asyncio.to_thread(self._create_instance, provider)

    async def cleanup_stale(self):
        await asyncio.to_thread(self._cleanup_stale)

    def _create_instance(self, provider: str) -> AgentRuntimeInstanceDirs:
        root = self._root / provider / INSTANCES_DIR / uuid4().hex
        dirs = AgentRuntimeInstanceDirs(
            root=root, home=root / "home", work=root / "work"
        )
        for path in (dirs.root, dirs.home, dirs.work):
            _ensure_private_dir(path)
        return dirs

    def _cleanup_stale(self):
        if not self._root.is_dir():
            return
        for provider_dir in self._root.iterdir():
            instances = provider_dir / INSTANCES_DIR
            if instances.is_dir():
                shutil.rmtree(instances, ignore_errors=True)
