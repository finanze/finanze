from enum import Enum
from typing import Any, Optional

from domain.entity import Entity, Feature
from domain.fetch_record import DataSource
from domain.global_position import GlobalPosition, ProductType
from domain.template import Template
from domain.transactions import Transactions
from pydantic.dataclasses import dataclass


@dataclass
class TemplatedDataParserParams:
    template: Template
    feature: Feature
    product: ProductType
    datetime_format: str
    date_format: str
    params: dict[str, Any]


@dataclass
class ImportCandidate:
    name: Optional[str]
    source: DataSource
    params: TemplatedDataParserParams
    data: list[list[str]]


class ImportResultCode(str, Enum):
    # Success
    COMPLETED = "COMPLETED"

    # Import not configured
    DISABLED = "DISABLED"


class ImportErrorType(str, Enum):
    SHEET_NOT_FOUND = "SHEET_NOT_FOUND"
    MISSING_FIELD = "MISSING_FIELD"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNEXPECTED_COLUMN = "UNEXPECTED_COLUMN"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


@dataclass
class ImportError:
    type: ImportErrorType
    entry: str
    detail: Optional[list[Any]] = None
    row: Optional[list[str]] = None


@dataclass
class ImportedData:
    positions: Optional[list[GlobalPosition]] = None
    transactions: Optional[Transactions] = None


@dataclass
class ImportResult:
    code: ImportResultCode
    data: Optional[ImportedData] = None
    errors: Optional[list[ImportError]] = None


@dataclass
class TransactionsImportResult:
    transactions: Optional[Transactions]
    created_entities: set[Entity]
    errors: list[ImportError]


@dataclass
class PositionImportResult:
    positions: list[GlobalPosition]
    created_entities: set[Entity]
    errors: list[ImportError]
