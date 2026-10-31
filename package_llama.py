import hashlib
import json
import logging
import os
import platform
import re
import shutil
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Optional

import httpx

logger = logging.getLogger("packager")

SERVER_NAME = "llama-server"
TARGET_NAME = "finanze-llama-server"
LICENSE_NAME = "LICENSE"
SHARED_LIBRARY = re.compile(r"\.(dylib|dll)$|\.so(\.\d+)*$")
DEV_LINK = re.compile(r"^lib[^.]+\.(dylib|so)$")
TOOL_LIBRARY = re.compile(r"^(lib)?llama-(?!server-impl\.).+-impl\.")
OS_NAMES = {"Darwin": "mac", "Linux": "linux", "Windows": "win"}
ARCH_NAMES = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}
DOWNLOAD_TIMEOUT = 120.0
LLAMA_LICENSE_PATH = Path(__file__).parent / "resources" / "llama" / LICENSE_NAME


class LlamaPackagingError(Exception):
    pass


def host_platform() -> tuple[str, str]:
    os_name = OS_NAMES.get(platform.system())
    arch = ARCH_NAMES.get(platform.machine().lower())
    if not os_name or not arch:
        raise LlamaPackagingError(
            f"Unsupported platform {platform.system()} {platform.machine()}"
        )
    return os_name, arch


def load_lock(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lock = json.load(f)
    except (OSError, ValueError) as e:
        raise LlamaPackagingError(f"Could not read {path}: {e}") from e
    if (
        not isinstance(lock, dict)
        or not str(lock.get("base_url", "")).startswith("https://")
        or not isinstance(lock.get("assets"), dict)
    ):
        raise LlamaPackagingError(f"Invalid llama.cpp lock file {path}")
    return lock


def select_asset(lock: dict, os_name: str, arch: str) -> dict:
    asset = lock["assets"].get(f"{os_name}-{arch}")
    if (
        not isinstance(asset, dict)
        or not asset.get("file")
        or not re.fullmatch(r"[0-9a-f]{64}", str(asset.get("sha256", "")))
    ):
        raise LlamaPackagingError(f"No llama.cpp asset for {os_name}-{arch}")
    return asset


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch(url: str, destination: Path):
    with httpx.stream(
        "GET", url, follow_redirects=True, timeout=DOWNLOAD_TIMEOUT
    ) as response:
        response.raise_for_status()
        with open(destination, "wb") as out:
            for chunk in response.iter_bytes():
                out.write(chunk)


def download_asset(
    lock: dict,
    asset: dict,
    cache_dir: Path,
    fetch: Callable[[str, Path], None] = _fetch,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive = cache_dir / asset["file"]
    if archive.is_file() and sha256(archive) == asset["sha256"]:
        logger.info(f"Using cached {archive.name}")
        return archive

    partial = cache_dir / f"{asset['file']}.part"
    logger.info(f"Downloading {asset['file']}")
    try:
        fetch(f"{lock['base_url']}/{asset['file']}", partial)
    except httpx.HTTPError as e:
        partial.unlink(missing_ok=True)
        raise LlamaPackagingError(f"Could not download {asset['file']}: {e}") from e
    if sha256(partial) != asset["sha256"]:
        partial.unlink(missing_ok=True)
        raise LlamaPackagingError(f"Checksum mismatch for {asset['file']}")
    os.replace(partial, archive)
    return archive


def extract(archive: Path, destination: Path):
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(destination)
    else:
        with tarfile.open(archive) as t:
            t.extractall(destination, filter="data")


def _find_server(root: Path) -> Path:
    candidates = [
        path
        for path in root.rglob(f"{SERVER_NAME}*")
        if path.name in (SERVER_NAME, f"{SERVER_NAME}.exe") and path.is_file()
    ]
    if len(candidates) != 1:
        raise LlamaPackagingError(
            f"Expected one {SERVER_NAME} binary, found {len(candidates)}"
        )
    return candidates[0]


def _make_executable(path: Path):
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _find_license(extracted: Path, source_dir: Path) -> Optional[Path]:
    return next(
        (
            path
            for path in (source_dir / LICENSE_NAME, extracted / LICENSE_NAME)
            if path.is_file()
        ),
        None,
    )


def install(
    extracted: Path, output: Path, license_fallback: Optional[Path] = None
) -> Path:
    server = _find_server(extracted)
    source_dir = server.parent
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    target = output / f"{TARGET_NAME}{server.suffix}"
    shutil.copy2(server, target)
    _make_executable(target)

    runtime_names: dict[Path, list[str]] = {}
    libraries: list[Path] = []
    for entry in sorted(source_dir.iterdir()):
        if not SHARED_LIBRARY.search(entry.name) or TOOL_LIBRARY.match(entry.name):
            continue
        if entry.is_symlink():
            if DEV_LINK.match(entry.name):
                continue
            real = entry.resolve()
            if real.parent == source_dir.resolve() and real.is_file():
                runtime_names.setdefault(real, []).append(entry.name)
        elif entry.is_file():
            libraries.append(entry)

    for library in libraries:
        for name in runtime_names.get(library.resolve(), [library.name]):
            shutil.copy2(library, output / name)
            _make_executable(output / name)

    license_file = _find_license(extracted, source_dir)
    if license_file is None and license_fallback and license_fallback.is_file():
        license_file = license_fallback
    if license_file is None:
        raise LlamaPackagingError("llama.cpp LICENSE not found in archive")
    shutil.copy2(license_file, output / LICENSE_NAME)
    for additional_license in source_dir.glob("LICENSE-*"):
        if additional_license.is_file():
            shutil.copy2(additional_license, output / additional_license.name)
    return target


def fetch_llama_server(
    lock_path: Path,
    output: Path,
    cache_dir: Path,
    os_name: Optional[str] = None,
    arch: Optional[str] = None,
    fetch: Callable[[str, Path], None] = _fetch,
) -> Path:
    if not os_name or not arch:
        host_os, host_arch = host_platform()
        os_name = os_name or host_os
        arch = arch or host_arch
    lock = load_lock(lock_path)
    asset = select_asset(lock, os_name, arch)
    archive = download_asset(lock, asset, cache_dir, fetch)
    with tempfile.TemporaryDirectory() as tmp:
        extracted = Path(tmp)
        extract(archive, extracted)
        server = _find_server(extracted)
        license_fallback = None
        if _find_license(extracted, server.parent) is None:
            expected_license_sha256 = lock.get("license_sha256")
            if (
                not LLAMA_LICENSE_PATH.is_file()
                or not isinstance(expected_license_sha256, str)
                or sha256(LLAMA_LICENSE_PATH) != expected_license_sha256
            ):
                raise LlamaPackagingError(
                    "llama.cpp LICENSE missing from archive and verified fallback"
                )
            license_fallback = LLAMA_LICENSE_PATH
        target = install(extracted, output, license_fallback)
    logger.info(f"llama.cpp server {lock.get('build')} ready at {target}")
    return target
