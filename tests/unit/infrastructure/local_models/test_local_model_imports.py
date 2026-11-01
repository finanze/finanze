import json
from pathlib import Path

import pytest
from domain.exception.exceptions import LocalModelError, LocalModelErrorCode
from infrastructure.local_models.local_model_imports import (
    LOCAL_FOLDER,
    MANIFEST_FILE,
    LocalModelFileImports,
    ensure_presets,
    presets_path,
)


def _gguf(path: Path, size: int = 16) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"GGUF" + b"\0" * (size - 4))
    return path


@pytest.fixture
def models_dir(tmp_path) -> Path:
    return tmp_path / "models"


@pytest.fixture
def imports(models_dir) -> LocalModelFileImports:
    return LocalModelFileImports(models_dir)


def _presets(models_dir: Path) -> str:
    return presets_path(models_dir).read_text()


class TestEnsurePresets:
    def test_creates_once(self, models_dir):
        ensure_presets(models_dir)
        assert _presets(models_dir) == "version = 1\n"
        presets_path(models_dir).write_text("custom")
        ensure_presets(models_dir)
        assert _presets(models_dir) == "custom"


class TestAdd:
    @pytest.mark.asyncio
    async def test_references_external_file(self, imports, models_dir, tmp_path):
        file = _gguf(tmp_path / "downloads" / "My Model Q4_K_M.gguf", size=32)
        model = await imports.add(str(file))
        assert model.id == "local/my-model-q4_k_m"
        assert model.path == str(file.resolve())
        assert model.exists is True
        assert model.size == 32
        manifest = json.loads((models_dir / MANIFEST_FILE).read_text())
        assert manifest == {"models": [{"id": model.id, "path": str(file.resolve())}]}
        assert _presets(models_dir) == (
            f"version = 1\n\n[local/my-model-q4_k_m]\nmodel = {file.resolve()}\n"
        )

    @pytest.mark.asyncio
    async def test_same_file_is_idempotent(self, imports, tmp_path):
        file = _gguf(tmp_path / "a.gguf")
        first = await imports.add(str(file))
        second = await imports.add(str(file))
        assert first.id == second.id
        assert len(await imports.list()) == 1

    @pytest.mark.asyncio
    async def test_unique_ids(self, imports, tmp_path):
        first = await imports.add(str(_gguf(tmp_path / "one" / "model.gguf")))
        second = await imports.add(str(_gguf(tmp_path / "two" / "model.gguf")))
        assert first.id == "local/model"
        assert second.id == "local/model-2"

    @pytest.mark.asyncio
    async def test_file_in_models_folder_is_not_referenced(self, imports, models_dir):
        file = _gguf(models_dir / LOCAL_FOLDER / "phi.gguf")
        model = await imports.add(str(file))
        assert model.id == "local/phi"
        assert not (models_dir / MANIFEST_FILE).exists()
        assert "[local/phi]" in _presets(models_dir)

    @pytest.mark.parametrize(
        "name, content",
        [
            ("model.bin", b"GGUF"),
            ("model.gguf", b"NOPE"),
            ("mmproj-model.gguf", b"GGUF"),
        ],
    )
    @pytest.mark.asyncio
    async def test_rejects_non_models(self, imports, tmp_path, name, content):
        file = tmp_path / name
        file.write_bytes(content)
        with pytest.raises(LocalModelError) as error:
            await imports.add(str(file))
        assert error.value.code == LocalModelErrorCode.INVALID_FILE

    @pytest.mark.parametrize(
        "path",
        [
            "",
            "   ",
            "relative/model.gguf",
            "/tmp/x\n[evil]\nmodel.gguf",
            "/tmp/a;b.gguf",
        ],
    )
    @pytest.mark.asyncio
    async def test_rejects_invalid_paths(self, imports, path):
        with pytest.raises(LocalModelError) as error:
            await imports.add(path)
        assert error.value.code == LocalModelErrorCode.INVALID_FILE

    @pytest.mark.asyncio
    async def test_rejects_missing_file(self, imports, tmp_path):
        with pytest.raises(LocalModelError):
            await imports.add(str(tmp_path / "missing.gguf"))


class TestList:
    @pytest.mark.asyncio
    async def test_lists_folder_and_references(self, imports, models_dir, tmp_path):
        _gguf(models_dir / LOCAL_FOLDER / "b.gguf")
        _gguf(models_dir / LOCAL_FOLDER / "mmproj-b.gguf")
        (models_dir / LOCAL_FOLDER / "notes.txt").write_text("x")
        external = await imports.add(str(_gguf(tmp_path / "a.gguf")))
        models = await imports.list()
        assert [m.id for m in models] == [external.id, "local/b"]

    @pytest.mark.asyncio
    async def test_missing_reference(self, imports, models_dir, tmp_path):
        file = _gguf(tmp_path / "gone.gguf")
        model = await imports.add(str(file))
        file.unlink()
        await imports.sync()
        listed = await imports.list()
        assert listed[0].id == model.id
        assert listed[0].exists is False
        assert listed[0].size is None
        assert model.id not in _presets(models_dir)

    @pytest.mark.asyncio
    async def test_corrupt_manifest(self, imports, models_dir):
        models_dir.mkdir(parents=True)
        (models_dir / MANIFEST_FILE).write_text("{not json")
        assert await imports.list() == []

    def test_folder_is_created(self, imports, models_dir):
        assert imports.folder() == str((models_dir / LOCAL_FOLDER).resolve())
        assert (models_dir / LOCAL_FOLDER).is_dir()

    def test_folder_is_absolute_for_relative_models_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        folder = LocalModelFileImports(Path("data") / "models").folder()
        assert folder == str((tmp_path / "data" / "models" / LOCAL_FOLDER).resolve())


class TestRemove:
    @pytest.mark.asyncio
    async def test_removes_reference_but_keeps_file(
        self, imports, models_dir, tmp_path
    ):
        file = _gguf(tmp_path / "a.gguf")
        model = await imports.add(str(file))
        assert await imports.remove(model.id) is True
        assert file.exists()
        assert await imports.list() == []
        assert _presets(models_dir) == "version = 1\n"

    @pytest.mark.asyncio
    async def test_deletes_folder_file(self, imports, models_dir):
        file = _gguf(models_dir / LOCAL_FOLDER / "b.gguf")
        assert await imports.remove("local/b") is True
        assert not file.exists()

    @pytest.mark.asyncio
    async def test_unknown(self, imports):
        assert await imports.remove("local/unknown") is False
