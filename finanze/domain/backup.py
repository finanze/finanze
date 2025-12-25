from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.cloud_auth import CloudAuthData

CURRENT_PROTOCOL_VERSION = 1


class BackupFileType(str, Enum):
    DATA = "DATA"
    CONFIG = "CONFIG"


class BackupMode(str, Enum):
    OFF = "OFF"
    MANUAL = "MANUAL"
    AUTO = "AUTO"


@dataclass
class BackupInfo:
    id: UUID
    protocol: int
    date: datetime
    type: BackupFileType
    size: int


@dataclass
class BackupsInfo:
    pieces: dict[BackupFileType, BackupInfo]


@dataclass
class BackupsInfoRequest:
    only_local: bool = False


class SyncStatus(str, Enum):
    SYNC = "SYNC"
    PENDING = "PENDING"
    OUTDATED = "OUTDATED"
    MISSING = "MISSING"
    CONFLICT = "CONFLICT"


@dataclass
class FullBackupInfo:
    local: Optional[BackupInfo]
    remote: Optional[BackupInfo]
    last_update: datetime
    has_local_changes: bool
    status: Optional[SyncStatus]


@dataclass
class FullBackupsInfo:
    pieces: dict[BackupFileType, FullBackupInfo]


@dataclass
class BackupProcessRequest:
    protocol: int
    password: str
    payload: bytes


@dataclass
class BackupProcessResult:
    payload: bytes


@dataclass
class BackupTransferPiece:
    id: UUID
    protocol: int
    date: datetime
    type: BackupFileType
    payload: bytes


@dataclass
class BackupPieces:
    pieces: list[BackupTransferPiece]


@dataclass
class BackupUploadParams:
    pieces: BackupPieces
    auth: CloudAuthData


@dataclass
class BackupDownloadParams:
    types: list[BackupFileType]
    auth: CloudAuthData


@dataclass
class BackupInfoParams:
    auth: CloudAuthData


@dataclass
class UploadBackupRequest:
    types: list[BackupFileType]
    force: bool = False


@dataclass
class ImportBackupRequest:
    types: list[BackupFileType]
    password: Optional[str]
    force: bool = False


@dataclass
class BackupSyncResult:
    pieces: dict[BackupFileType, FullBackupInfo]


@dataclass
class BackupSettings:
    mode: BackupMode
