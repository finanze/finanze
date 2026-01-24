from dataclasses import dataclass
from enum import Enum
from typing import Optional, TypeAlias

from domain.user import User


class FFStatus(str, Enum):
    ON = "ON"
    OFF = "OFF"


FFValue = FFStatus | str

FeatureFlags: TypeAlias = dict[str, FFValue]


class LoginStatusCode(str, Enum):
    LOCKED = "LOCKED"
    UNLOCKED = "UNLOCKED"


class BackendLogLevel(str, Enum):
    NONE = "NONE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class BackendOptions:
    data_dir: Optional[str] = None
    port: Optional[int] = None
    log_level: Optional[BackendLogLevel] = None
    log_dir: Optional[str] = None
    log_file_level: Optional[BackendLogLevel] = None
    third_party_log_level: Optional[BackendLogLevel] = None


@dataclass
class BackendDetails:
    version: str
    options: BackendOptions


@dataclass
class GlobalStatus:
    status: LoginStatusCode
    server: BackendDetails
    features: FeatureFlags
    user: Optional[User] = None
    last_logged: Optional[str] = None
