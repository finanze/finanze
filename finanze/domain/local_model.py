import re
from dataclasses import field
from enum import Enum
from typing import Optional

from domain.exception.exceptions import LocalModelError, LocalModelErrorCode
from pydantic.dataclasses import dataclass

HUGGING_FACE_REPO_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$"
)
QUANT_TAG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,31}$")
IMPORTED_MODEL_PREFIX = "local/"


def hugging_face_model_id(repo: str, quant: str) -> str:
    repo = (repo or "").strip()
    quant = (quant or "").strip()
    if not HUGGING_FACE_REPO_PATTERN.match(repo) or not QUANT_TAG_PATTERN.match(quant):
        raise LocalModelError(LocalModelErrorCode.INVALID_MODEL)
    return f"{repo}:{quant}"


def is_hugging_face_model_id(model_id: str) -> bool:
    repo, separator, quant = model_id.rpartition(":")
    return (
        bool(separator)
        and HUGGING_FACE_REPO_PATTERN.match(repo) is not None
        and QUANT_TAG_PATTERN.match(quant) is not None
    )


def is_imported_model_id(model_id: str) -> bool:
    return model_id.startswith(IMPORTED_MODEL_PREFIX)


class LocalModelSource(str, Enum):
    CATALOG = "CATALOG"
    HUGGING_FACE = "HUGGING_FACE"
    IMPORTED = "IMPORTED"
    SERVER = "SERVER"


class LocalModelState(str, Enum):
    UNLOADED = "UNLOADED"
    LOADING = "LOADING"
    LOADED = "LOADED"
    SLEEPING = "SLEEPING"
    DOWNLOADING = "DOWNLOADING"
    FAILED = "FAILED"
    MISSING = "MISSING"


USABLE_LOCAL_MODEL_STATES = {
    LocalModelState.UNLOADED,
    LocalModelState.LOADING,
    LocalModelState.LOADED,
    LocalModelState.SLEEPING,
    LocalModelState.FAILED,
}


class LocalRuntimeMode(str, Enum):
    BUILT_IN = "BUILT_IN"
    EXTERNAL = "EXTERNAL"


class LocalRuntimeSource(str, Enum):
    PAYLOAD = "PAYLOAD"
    ENVIRONMENT = "ENVIRONMENT"
    BUILT_IN = "BUILT_IN"


@dataclass
class LocalRouterConnection:
    base_url: str
    mode: LocalRuntimeMode
    source: LocalRuntimeSource
    api_key: Optional[str] = None


@dataclass
class LocalRouterModel:
    id: str
    state: LocalModelState
    size: Optional[int] = None
    downloaded: Optional[int] = None
    decisions: bool = False
    removable: Optional[bool] = None


@dataclass
class ImportedLocalModel:
    id: str
    path: str
    exists: bool = True
    size: Optional[int] = None


@dataclass
class LocalModel:
    id: str
    name: str
    source: LocalModelSource
    state: LocalModelState
    size: Optional[int] = None
    downloaded: Optional[int] = None
    decisions: bool = False
    deletable: bool = False
    path: Optional[str] = None


@dataclass
class LocalModelCatalogEntry:
    id: str
    name: str
    repo: str
    quant: str
    size: int
    ram: int
    params: str
    license: str
    decisions: bool = False
    languages: Optional[list[str]] = None


@dataclass
class HuggingFaceQuantOption:
    quant: str
    file: str
    size: Optional[int] = None


class HuggingFaceModelKind(str, Enum):
    DECISIONS = "DECISIONS"
    CHAT = "CHAT"
    ENCODER = "ENCODER"
    UNKNOWN = "UNKNOWN"


@dataclass
class HuggingFaceQuants:
    repo: str
    quants: list[HuggingFaceQuantOption]
    kind: HuggingFaceModelKind = HuggingFaceModelKind.UNKNOWN


@dataclass
class LocalModelsCapabilities:
    built_in_available: bool
    can_import_files: bool
    env_server_url: Optional[str] = None
    env_api_key_set: bool = False
    system_memory: Optional[int] = None


@dataclass
class LocalModelsOverview:
    connected: bool
    capabilities: LocalModelsCapabilities
    catalog: list[LocalModelCatalogEntry]
    mode: Optional[LocalRuntimeMode] = None
    source: Optional[LocalRuntimeSource] = None
    server_url: Optional[str] = None
    reachable: bool = False
    error: Optional[LocalModelErrorCode] = None
    models: list[LocalModel] = field(default_factory=list)
    models_folder: Optional[str] = None


@dataclass
class DownloadLocalModelRequest:
    catalog_id: Optional[str] = None
    repo: Optional[str] = None
    quant: Optional[str] = None


@dataclass
class LocalModelRequest:
    model_id: str


@dataclass
class ImportLocalModelRequest:
    path: str
