from dataclasses import field
from enum import Enum
from typing import Optional

from pydantic import StrictBool
from pydantic.dataclasses import dataclass


class McpAccess(str, Enum):
    DISABLED = "DISABLED"
    LOCKED = "LOCKED"
    UNAUTHORIZED = "UNAUTHORIZED"
    READ_ONLY = "READ_ONLY"
    READ_WRITE = "READ_WRITE"


class McpToolCategory(str, Enum):
    POSITIONS = "positions"
    TRANSACTIONS = "transactions"
    ACTIVITY_LABELS = "activity_labels"
    BUDGET = "budget"
    CRYPTO = "crypto"
    REAL_ESTATE = "real_estate"
    MARKET_DATA = "market_data"
    CALCULATORS = "calculators"
    CONNECTIONS = "connections"


@dataclass
class McpCategoryAccess:
    read_enabled: StrictBool = True
    write_enabled: StrictBool = True

    def __post_init__(self):
        if self.write_enabled and not self.read_enabled:
            raise ValueError("Write access requires read access")


@dataclass
class McpConfig:
    enabled: bool = False
    read_only: bool = True
    token: Optional[str] = None
    category_access: dict[McpToolCategory, McpCategoryAccess] = field(
        default_factory=dict
    )


@dataclass
class UpdateMcpConfigRequest:
    enabled: bool
    read_only: bool
    category_access: Optional[dict[McpToolCategory, McpCategoryAccess]] = None


@dataclass
class McpAuthorization:
    access: McpAccess
    category_access: dict[McpToolCategory, McpCategoryAccess] = field(
        default_factory=dict
    )
