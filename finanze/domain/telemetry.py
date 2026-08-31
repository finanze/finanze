from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.platform import OS


class TelemetryLevel(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class TelemetryConsent:
    error_reporting: bool = False
    session_replay: bool = False
    install_id: Optional[UUID] = None
    updated_at: Optional[datetime] = None


@dataclass
class TelemetryContext:
    environment: str
    release: Optional[str] = None
    operative_system: Optional[OS] = None
    install_id: Optional[UUID] = None
    user_hash: Optional[str] = None
