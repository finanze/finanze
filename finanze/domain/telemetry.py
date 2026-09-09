from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.platform import OS, Distribution


class TelemetryLevel(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class TelemetryConsent:
    error_reporting: bool = False
    install_id: Optional[UUID] = None
    updated_at: Optional[datetime] = None


@dataclass
class TelemetryContext:
    environment: str
    release: Optional[str] = None
    operative_system: Optional[OS] = None
    os_version: Optional[str] = None
    distribution: Optional[Distribution] = None
    install_id: Optional[UUID] = None
    user_hash: Optional[str] = None
