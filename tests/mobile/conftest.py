import base64
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

MOBILE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "app"
    / "src"
    / "python"
    / "finanze"
)


class FakePreferences:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.error: Exception | None = None

    def reset(self):
        self.values.clear()
        self.error = None

    async def get(self, key: str):
        if self.error:
            raise self.error
        return self.values.get(key)


class FakeBackupProcessorPlugin:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def reset(self):
        self.files.clear()
        self.deleted.clear()

    async def readFile(self, options):
        name = options["fileName"]
        if name not in self.files:
            raise RuntimeError(f"FILE_NOT_FOUND: {name}")
        return {"data": base64.b64encode(self.files[name]).decode("ascii")}

    async def deleteFile(self, options):
        name = options["fileName"]
        self.deleted.append(name)
        self.files.pop(name, None)


PREFERENCES = FakePreferences()
BACKUP_PLUGIN = FakeBackupProcessorPlugin()


def _install_fake_pyodide():
    js_module = types.ModuleType("js")
    js_module.jsBridge = SimpleNamespace(preferences=PREFERENCES)
    js_module.window = SimpleNamespace(BackupProcessor=BACKUP_PLUGIN)

    pyodide_module = types.ModuleType("pyodide")
    ffi_module = types.ModuleType("pyodide.ffi")
    ffi_module.to_js = lambda value, **_: value
    pyodide_module.ffi = ffi_module

    sys.modules.setdefault("js", js_module)
    sys.modules.setdefault("pyodide", pyodide_module)
    sys.modules.setdefault("pyodide.ffi", ffi_module)

    if str(MOBILE_ROOT) not in sys.path:
        sys.path.append(str(MOBILE_ROOT))


_install_fake_pyodide()


@pytest.fixture
def preferences():
    PREFERENCES.reset()
    yield PREFERENCES
    PREFERENCES.reset()


@pytest.fixture
def backup_plugin():
    BACKUP_PLUGIN.reset()
    yield BACKUP_PLUGIN
    BACKUP_PLUGIN.reset()
