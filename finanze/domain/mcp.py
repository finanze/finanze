from enum import Enum
from typing import Optional

from pydantic.dataclasses import dataclass


class McpAccess(str, Enum):
    DISABLED = "DISABLED"
    LOCKED = "LOCKED"
    UNAUTHORIZED = "UNAUTHORIZED"
    READ_ONLY = "READ_ONLY"
    READ_WRITE = "READ_WRITE"


@dataclass
class McpConfig:
    enabled: bool = False
    read_only: bool = True
    token: Optional[str] = None


@dataclass
class UpdateMcpConfigRequest:
    enabled: bool
    read_only: bool
