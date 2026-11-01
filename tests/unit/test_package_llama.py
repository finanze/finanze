import hashlib
import io
import json
import os
import tarfile
import zipfile
from pathlib import Path

import httpx
import pytest
from package_llama import (
    LLAMA_LICENSE_PATH,
    TARGET_NAME,
    LlamaPackagingError,
    download_asset,
    fetch_llama_server,
    install,
    load_lock,
    select_asset,
)

LOCK_FILE = Path(__file__).parents[2] / "resources" / "llama-server.lock.json"
BASE_URL = "https://example.com/releases/b1"


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _write_lock(
    path: Path,
    assets: dict,
    base_url: str = BASE_URL,
    license_sha256: str | None = None,
) -> Path:
    lock = {"build": "b1", "base_url": base_url, "assets": assets}
    if license_sha256 is not None:
        lock["license_sha256"] = license_sha256
    path.write_text(json.dumps(lock))
    return path


def _tar(files: dict[str, bytes], links: dict[str, str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))
        for name, target in (links or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            archive.addfile(info)
    return buffer.getvalue()


def _zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class FakeFetch:
    def __init__(self, content: bytes = b"", error: Exception | None = None):
        self.content = content
        self.error = error
        self.urls: list[str] = []

    def __call__(self, url: str, destination: Path):
        self.urls.append(url)
        destination.write_bytes(self.content)
        if self.error:
            raise self.error


class TestLock:
    def test_repository_lock_pins_bundled_license(self):
        lock = load_lock(LOCK_FILE)
        assert lock["license_sha256"] == _sha(LLAMA_LICENSE_PATH.read_bytes())

    def test_repository_lock_is_valid(self):
        lock = load_lock(LOCK_FILE)
        for platform in ("mac", "linux", "win"):
            for arch in ("x64", "arm64"):
                assert select_asset(lock, platform, arch)["file"]

    @pytest.mark.parametrize(
        "content",
        [
            "not json",
            "[]",
            json.dumps({"base_url": "http://insecure", "assets": {}}),
            json.dumps({"base_url": BASE_URL, "assets": []}),
            json.dumps({"assets": {}}),
        ],
    )
    def test_invalid_lock(self, tmp_path, content):
        path = tmp_path / "lock.json"
        path.write_text(content)
        with pytest.raises(LlamaPackagingError):
            load_lock(path)

    def test_missing_lock(self, tmp_path):
        with pytest.raises(LlamaPackagingError):
            load_lock(tmp_path / "missing.json")

    @pytest.mark.parametrize(
        "asset",
        [
            None,
            {"sha256": "a" * 64},
            {"file": "a.tar.gz", "sha256": "short"},
            {"file": "a.tar.gz", "sha256": "A" * 64},
        ],
    )
    def test_invalid_asset(self, asset):
        lock = {"assets": {"mac-arm64": asset} if asset else {}}
        with pytest.raises(LlamaPackagingError):
            select_asset(lock, "mac", "arm64")


class TestDownload:
    def _asset(self, content: bytes) -> dict:
        return {"file": "llama.tar.gz", "sha256": _sha(content)}

    def test_downloads_and_verifies(self, tmp_path):
        fetch = FakeFetch(b"archive")
        archive = download_asset(
            {"base_url": BASE_URL}, self._asset(b"archive"), tmp_path, fetch
        )
        assert archive == tmp_path / "llama.tar.gz"
        assert archive.read_bytes() == b"archive"
        assert fetch.urls == [f"{BASE_URL}/llama.tar.gz"]
        assert not (tmp_path / "llama.tar.gz.part").exists()

    def test_reuses_cached_archive(self, tmp_path):
        (tmp_path / "llama.tar.gz").write_bytes(b"archive")
        fetch = FakeFetch()
        download_asset({"base_url": BASE_URL}, self._asset(b"archive"), tmp_path, fetch)
        assert fetch.urls == []

    def test_replaces_corrupt_cache(self, tmp_path):
        (tmp_path / "llama.tar.gz").write_bytes(b"corrupt")
        fetch = FakeFetch(b"archive")
        archive = download_asset(
            {"base_url": BASE_URL}, self._asset(b"archive"), tmp_path, fetch
        )
        assert archive.read_bytes() == b"archive"
        assert len(fetch.urls) == 1

    def test_checksum_mismatch(self, tmp_path):
        with pytest.raises(LlamaPackagingError, match="Checksum"):
            download_asset(
                {"base_url": BASE_URL},
                self._asset(b"expected"),
                tmp_path,
                FakeFetch(b"tampered"),
            )
        assert list(tmp_path.iterdir()) == []

    def test_http_error(self, tmp_path):
        fetch = FakeFetch(b"partial", error=httpx.ConnectError("down"))
        with pytest.raises(LlamaPackagingError, match="Could not download"):
            download_asset(
                {"base_url": BASE_URL}, self._asset(b"archive"), tmp_path, fetch
            )
        assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlinks")
class TestInstall:
    def _extracted(self, tmp_path: Path) -> Path:
        root = tmp_path / "extracted"
        bin_dir = root / "build" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "llama-server").write_bytes(b"server")
        (bin_dir / "llama-cli").write_bytes(b"cli")
        (bin_dir / "libggml-base.0.9.4.dylib").write_bytes(b"ggml-base")
        (bin_dir / "libggml-base.0.dylib").symlink_to("libggml-base.0.9.4.dylib")
        (bin_dir / "libggml-base.dylib").symlink_to("libggml-base.0.dylib")
        (bin_dir / "libllama.so.0").write_bytes(b"llama")
        (bin_dir / "libggml-cpu.so").write_bytes(b"cpu")
        (bin_dir / "libllama-server-impl.so").write_bytes(b"server-impl")
        (bin_dir / "libllama-cli-impl.so").write_bytes(b"cli-impl")
        (bin_dir / "README.md").write_text("readme")
        (bin_dir / "LICENSE").write_text("MIT")
        return root

    def test_installs_runtime_files(self, tmp_path):
        output = tmp_path / "out"
        (output / "stale").mkdir(parents=True)

        target = install(self._extracted(tmp_path), output)

        assert target == output / TARGET_NAME
        assert target.read_bytes() == b"server"
        assert os.access(target, os.X_OK)
        assert sorted(p.name for p in output.iterdir()) == [
            "LICENSE",
            TARGET_NAME,
            "libggml-base.0.dylib",
            "libggml-cpu.so",
            "libllama-server-impl.so",
            "libllama.so.0",
        ]
        assert not any(p.is_symlink() for p in output.iterdir())
        assert (output / "libggml-base.0.dylib").read_bytes() == b"ggml-base"
        assert (output / "LICENSE").read_text() == "MIT"

    def test_license_at_archive_root(self, tmp_path):
        extracted = self._extracted(tmp_path)
        license_file = extracted / "build" / "bin" / "LICENSE"
        license_file.rename(extracted / "LICENSE")
        install(extracted, tmp_path / "out")
        assert (tmp_path / "out" / "LICENSE").read_text() == "MIT"

    def test_requires_license(self, tmp_path):
        extracted = self._extracted(tmp_path)
        (extracted / "build" / "bin" / "LICENSE").unlink()
        with pytest.raises(LlamaPackagingError, match="LICENSE"):
            install(extracted, tmp_path / "out")

    @pytest.mark.parametrize("servers", [0, 2])
    def test_requires_single_server(self, tmp_path, servers):
        root = tmp_path / "extracted"
        for index in range(servers):
            (root / str(index)).mkdir(parents=True)
            (root / str(index) / "llama-server").write_bytes(b"server")
        root.mkdir(exist_ok=True)
        with pytest.raises(LlamaPackagingError, match="llama-server"):
            install(root, tmp_path / "out")


class TestFetch:
    def test_tar_archive(self, tmp_path):
        content = _tar(
            {
                "llama-b1/llama-server": b"server",
                "llama-b1/libllama.0.dylib": b"llama",
                "llama-b1/LICENSE": b"MIT",
            },
            links={"llama-b1/libllama.dylib": "libllama.0.dylib"},
        )
        lock = _write_lock(
            tmp_path / "lock.json",
            {"mac-arm64": {"file": "llama.tar.gz", "sha256": _sha(content)}},
        )
        target = fetch_llama_server(
            lock,
            tmp_path / "out",
            tmp_path / "cache",
            "mac",
            "arm64",
            FakeFetch(content),
        )
        assert target.read_bytes() == b"server"
        assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [
            "LICENSE",
            TARGET_NAME,
            "libllama.0.dylib",
        ]

    def test_zip_archive(self, tmp_path):
        content = _zip(
            {
                "llama-server.exe": b"server",
                "ggml.dll": b"ggml",
                "llama-cli-impl.dll": b"cli",
                "LICENSE": b"MIT",
                "LICENSE-LLVM-OpenMP": b"LLVM OpenMP",
            }
        )
        lock = _write_lock(
            tmp_path / "lock.json",
            {"win-x64": {"file": "llama.zip", "sha256": _sha(content)}},
        )
        target = fetch_llama_server(
            lock, tmp_path / "out", tmp_path / "cache", "win", "x64", FakeFetch(content)
        )
        assert target.name == f"{TARGET_NAME}.exe"
        assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [
            "LICENSE",
            "LICENSE-LLVM-OpenMP",
            f"{TARGET_NAME}.exe",
            "ggml.dll",
        ]

    def test_zip_archive_uses_bundled_license_when_missing(self, tmp_path):
        content = _zip(
            {
                "llama-server.exe": b"server",
                "LICENSE-LLVM-OpenMP": b"LLVM OpenMP",
            }
        )
        bundled_license = Path(__file__).parents[2] / "resources" / "llama" / "LICENSE"
        lock = _write_lock(
            tmp_path / "lock.json",
            {"win-x64": {"file": "llama.zip", "sha256": _sha(content)}},
            license_sha256=_sha(bundled_license.read_bytes()),
        )
        target = fetch_llama_server(
            lock,
            tmp_path / "out",
            tmp_path / "cache",
            "win",
            "x64",
            FakeFetch(content),
        )
        assert target.name == f"{TARGET_NAME}.exe"
        assert (
            tmp_path / "out" / "LICENSE"
        ).read_bytes() == bundled_license.read_bytes()
        assert (tmp_path / "out" / "LICENSE-LLVM-OpenMP").read_bytes() == b"LLVM OpenMP"

    def test_unknown_platform(self, tmp_path):
        lock = _write_lock(tmp_path / "lock.json", {})
        with pytest.raises(LlamaPackagingError, match="No llama.cpp asset"):
            fetch_llama_server(
                lock, tmp_path / "out", tmp_path / "cache", "mac", "arm64", FakeFetch()
            )
