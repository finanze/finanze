import logging
import re
from typing import Optional

from application.ports.huggingface_catalog import HuggingFaceCatalog
from domain.exception.exceptions import LocalModelError, LocalModelErrorCode
from domain.local_model import (
    HUGGING_FACE_REPO_PATTERN,
    HuggingFaceModelKind,
    HuggingFaceQuantOption,
    HuggingFaceQuants,
)
from infrastructure.client.ai.server_url import TRANSPORT_ERRORS
from infrastructure.client.http.http_session import get_http_session

HUGGING_FACE_URL = "https://huggingface.co"
REPO_URL_PREFIXES = (
    "https://huggingface.co/",
    "http://huggingface.co/",
    "https://hf.co/",
    "huggingface.co/",
    "hf.co/",
)
GGUF_SUFFIX = ".gguf"
SPLIT_PATTERN = re.compile(r"^(.+)-([0-9]{5})-of-([0-9]{5})$", re.IGNORECASE)
TAG_PATTERN = re.compile(r"[-.]([A-Z0-9_]+)$", re.IGNORECASE)
SIDECAR_KEYWORDS = ("mmproj", "mtp-", "dflash-", "eagle3-", "dspark-")
MODEL_INFO_PARAMS = [
    ("blobs", "true"),
    ("expand[]", "siblings"),
    ("expand[]", "gguf"),
]


def normalize_repo(repo: str) -> str:
    value = (repo or "").strip()
    for prefix in REPO_URL_PREFIXES:
        if value.lower().startswith(prefix):
            value = value[len(prefix) :]
            break
    value = value.split("?")[0].strip("/")
    parts = value.split("/")
    if len(parts) > 2:
        value = "/".join(parts[:2])
    if not HUGGING_FACE_REPO_PATTERN.match(value):
        raise LocalModelError(LocalModelErrorCode.INVALID_MODEL, "Invalid repository")
    return value


def _is_sidecar(name: str) -> bool:
    return any(keyword in name for keyword in SIDECAR_KEYWORDS)


def _split_info(path: str) -> Optional[tuple[str, str, int, int]]:
    if not path.endswith(GGUF_SUFFIX):
        return None
    prefix = path[: -len(GGUF_SUFFIX)]
    index, count = 1, 1
    split = SPLIT_PATTERN.fullmatch(prefix)
    if split:
        prefix, index, count = split.group(1), int(split.group(2)), int(split.group(3))
    tag = TAG_PATTERN.search(prefix)
    return prefix, tag.group(1).upper() if tag else "", index, count


def listed_tag(path: str) -> Optional[str]:
    info = _split_info(path)
    if info is None:
        return None
    prefix, tag, index, count = info
    if count > 1 or not tag or _is_sidecar(prefix):
        return None
    return tag


def resolve_tag_file(paths: list[str], tag: str) -> Optional[str]:
    pattern = re.compile(re.escape(tag) + "[.-]", re.IGNORECASE)
    for path in paths:
        name = path.rsplit("/", 1)[-1]
        if "imatrix" in name or _is_sidecar(name) or not pattern.search(path):
            continue
        info = _split_info(path)
        if info is not None and info[2] == 1:
            return path
    return None


def model_kind(gguf) -> HuggingFaceModelKind:
    if not isinstance(gguf, dict) or not gguf.get("architecture"):
        return HuggingFaceModelKind.UNKNOWN
    if gguf.get("decision_type"):
        return HuggingFaceModelKind.DECISIONS
    if gguf.get("causal") is False:
        return HuggingFaceModelKind.ENCODER
    return HuggingFaceModelKind.CHAT


class HuggingFaceCatalogClient(HuggingFaceCatalog):
    TIMEOUT_SECONDS = 20.0

    def __init__(self):
        self._session = get_http_session()
        self._log = logging.getLogger(__name__)

    async def list_quants(self, repo: str) -> HuggingFaceQuants:
        repo = normalize_repo(repo)
        try:
            response = await self._session.get(
                f"{HUGGING_FACE_URL}/api/models/{repo}",
                params=MODEL_INFO_PARAMS,
                timeout=self.TIMEOUT_SECONDS,
            )
        except TRANSPORT_ERRORS as e:
            raise LocalModelError(
                LocalModelErrorCode.HUGGING_FACE_UNAVAILABLE, type(e).__name__
            ) from e

        if response.status in (401, 403, 404):
            raise LocalModelError(
                LocalModelErrorCode.INVALID_MODEL, "Repository not found or gated"
            )
        if not response.ok:
            self._log.warning(f"Hugging Face model request failed: {response.status}")
            raise LocalModelError(LocalModelErrorCode.HUGGING_FACE_UNAVAILABLE)

        try:
            info = await response.json()
        except ValueError:
            raise LocalModelError(LocalModelErrorCode.HUGGING_FACE_UNAVAILABLE)
        if not isinstance(info, dict):
            raise LocalModelError(LocalModelErrorCode.HUGGING_FACE_UNAVAILABLE)

        sizes: dict[str, Optional[int]] = {}
        siblings = info.get("siblings")
        for item in siblings if isinstance(siblings, list) else []:
            if not isinstance(item, dict):
                continue
            path = item.get("rfilename")
            if not isinstance(path, str) or not path:
                continue
            lfs = item.get("lfs") if isinstance(item.get("lfs"), dict) else {}
            size = lfs.get("size") or item.get("size")
            sizes[path] = int(size) if size else None

        paths = list(sizes)
        quants: dict[str, HuggingFaceQuantOption] = {}
        for path in paths:
            quant = listed_tag(path)
            if quant is None or quant in quants:
                continue
            file = resolve_tag_file(paths, quant)
            if file is None or listed_tag(file) != quant:
                continue
            quants[quant] = HuggingFaceQuantOption(
                quant=quant, file=file, size=sizes[file]
            )

        if not quants:
            raise LocalModelError(
                LocalModelErrorCode.INVALID_MODEL, "No GGUF files found"
            )

        return HuggingFaceQuants(
            repo=repo,
            quants=sorted(quants.values(), key=lambda q: (q.size is None, q.size or 0)),
            kind=model_kind(info.get("gguf")),
        )
