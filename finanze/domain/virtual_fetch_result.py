from enum import Enum
from typing import Any, Optional

from domain.entity import Entity
from domain.global_position import GlobalPosition
from domain.transactions import Transactions
from pydantic.dataclasses import dataclass


class VirtualFetchResultCode(str, Enum):
    # Success
    COMPLETED = "COMPLETED"

    # Virtual fetch not enabled
    DISABLED = "DISABLED"


class VirtualFetchErrorType(str, Enum):
    SHEET_NOT_FOUND = "SHEET_NOT_FOUND"
    MISSING_FIELD = "MISSING_FIELD"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


@dataclass
class VirtualFetchError:
    type: VirtualFetchErrorType
    entry: str
    detail: Optional[list[Any]] = None
    row: Optional[list[str]] = None


@dataclass
class VirtuallyFetchedData:
    positions: Optional[list[GlobalPosition]] = None
    transactions: Optional[Transactions] = None


@dataclass
class VirtualFetchResult:
    code: VirtualFetchResultCode
    data: Optional[VirtuallyFetchedData] = None
    errors: Optional[list[VirtualFetchError]] = None


@dataclass
class VirtualTransactionResult:
    transactions: Optional[Transactions]
    created_entities: set[Entity]
    errors: list[VirtualFetchError]


@dataclass
class VirtualPositionResult:
    positions: list[GlobalPosition]
    created_entities: set[Entity]
    errors: list[VirtualFetchError]
