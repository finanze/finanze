import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

from application.ports.local_model_imports import LocalModelImports
from domain.exception.exceptions import LocalModelError, LocalModelErrorCode
from domain.local_model import IMPORTED_MODEL_PREFIX, ImportedLocalModel

GGUF_MAGIC = b"GGUF"
FORBIDDEN_PATH_CHARS = ("\n", "\r", ";", "#", "[", "]")
PRESET_FILE = "finanze-presets.ini"
MANIFEST_FILE = "imports.json"
LOCAL_FOLDER = "local"


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-.")
    return slug[:64] or "model"


def _is_model_file(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".gguf") and "mmproj" not in name


def _imported(model_id: str, path: str) -> ImportedLocalModel:
    try:
        size = os.stat(path).st_size
    except OSError:
        return ImportedLocalModel(id=model_id, path=path, exists=False)
    return ImportedLocalModel(id=model_id, path=path, exists=True, size=size)


def _atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def presets_path(models_dir: Path) -> Path:
    return models_dir / PRESET_FILE


def ensure_presets(models_dir: Path):
    path = presets_path(models_dir)
    if not path.exists():
        _atomic_write(path, "version = 1\n")


class LocalModelFileImports(LocalModelImports):
    def __init__(self, models_dir: Path):
        self._models_dir = models_dir
        self._local_dir = models_dir / LOCAL_FOLDER
        self._manifest = models_dir / MANIFEST_FILE
        self._log = logging.getLogger(__name__)

    def folder(self) -> str:
        self._local_dir.mkdir(parents=True, exist_ok=True)
        return str(self._local_dir.resolve())

    async def list(self) -> list[ImportedLocalModel]:
        return self._collect()

    async def add(self, path: str) -> ImportedLocalModel:
        file = self._validate(path)
        models = self._collect()
        existing = next(
            (m for m in models if self._same_file(m.path, file)),
            None,
        )
        if existing is not None:
            await self.sync()
            return existing

        model_id = self._unique_id(_slug(file.stem), {m.id for m in models})
        references = self._read_manifest()
        references.append({"id": model_id, "path": str(file)})
        self._write_manifest(references)
        await self.sync()
        return _imported(model_id, str(file))

    async def remove(self, model_id: str) -> bool:
        references = self._read_manifest()
        remaining = [r for r in references if r.get("id") != model_id]
        if len(remaining) != len(references):
            self._write_manifest(remaining)
            await self.sync()
            return True

        model = next((m for m in self._folder_models() if m.id == model_id), None)
        if model is None:
            return False
        try:
            os.unlink(model.path)
        except FileNotFoundError:
            pass
        except OSError as e:
            raise LocalModelError(LocalModelErrorCode.INVALID_FILE, str(e)) from e
        await self.sync()
        return True

    async def sync(self):
        lines = ["version = 1", ""]
        for model in self._collect():
            if not model.exists:
                continue
            lines.append(f"[{model.id}]")
            lines.append(f"model = {model.path}")
            lines.append("")
        _atomic_write(presets_path(self._models_dir), "\n".join(lines))

    def _collect(self) -> list[ImportedLocalModel]:
        models = []
        used = set()
        for reference in self._read_manifest():
            model_id = reference.get("id")
            path = reference.get("path")
            if not model_id or not path or model_id in used:
                continue
            used.add(model_id)
            models.append(_imported(model_id, path))
        for model in self._folder_models(used):
            used.add(model.id)
            models.append(model)
        return models

    def _folder_models(
        self, used: Optional[set[str]] = None
    ) -> list[ImportedLocalModel]:
        used = set(used or ())
        if not self._local_dir.is_dir():
            return []
        models = []
        for file in sorted(self._local_dir.iterdir()):
            if not file.is_file() or not _is_model_file(file):
                continue
            if any(c in str(file) for c in FORBIDDEN_PATH_CHARS):
                continue
            model_id = self._unique_id(_slug(file.stem), used)
            used.add(model_id)
            models.append(_imported(model_id, str(file.resolve())))
        return models

    @staticmethod
    def _unique_id(slug: str, used: set[str]) -> str:
        candidate = f"{IMPORTED_MODEL_PREFIX}{slug}"
        index = 2
        while candidate in used:
            candidate = f"{IMPORTED_MODEL_PREFIX}{slug}-{index}"
            index += 1
        return candidate

    @staticmethod
    def _same_file(path: str, file: Path) -> bool:
        try:
            return Path(path).resolve() == file
        except OSError:
            return False

    @staticmethod
    def _validate(path: str) -> Path:
        raw = (path or "").strip()
        if not raw or any(c in raw for c in FORBIDDEN_PATH_CHARS):
            raise LocalModelError(LocalModelErrorCode.INVALID_FILE, "Invalid path")
        file = Path(raw).expanduser()
        if not file.is_absolute():
            raise LocalModelError(LocalModelErrorCode.INVALID_FILE, "Path not absolute")
        file = file.resolve()
        if not file.is_file() or not _is_model_file(file):
            raise LocalModelError(LocalModelErrorCode.INVALID_FILE, "Not a GGUF model")
        try:
            with open(file, "rb") as f:
                magic = f.read(len(GGUF_MAGIC))
        except OSError as e:
            raise LocalModelError(LocalModelErrorCode.INVALID_FILE, str(e)) from e
        if magic != GGUF_MAGIC:
            raise LocalModelError(LocalModelErrorCode.INVALID_FILE, "Not a GGUF model")
        return file

    def _read_manifest(self) -> list[dict]:
        if not self._manifest.exists():
            return []
        try:
            with open(self._manifest, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            self._log.warning(f"Could not read local models manifest: {e}")
            return []
        models = data.get("models") if isinstance(data, dict) else None
        return [m for m in models or [] if isinstance(m, dict)]

    def _write_manifest(self, references: list[dict]):
        _atomic_write(self._manifest, json.dumps({"models": references}, indent=2))
