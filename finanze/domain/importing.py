from dataclasses import field
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.entity import Entity, Feature
from domain.export import NumberFormat
from domain.fetch_record import DataSource
from domain.file_upload import FileUpload
from domain.global_position import GlobalPosition, ProductType
from domain.settings import TemplateConfig
from domain.template import Template, TemplatedField
from domain.transactions import BaseTx, Transactions, TxRefKey, TxType
from pydantic.dataclasses import dataclass

IMPORT_TX_TYPES_BY_PRODUCT: dict[ProductType, set[TxType]] = {
    ProductType.ACCOUNT: {TxType.INFLOW, TxType.OUTFLOW, TxType.INTEREST, TxType.FEE},
    ProductType.CRYPTO: {TxType.BUY, TxType.SELL, TxType.DIVIDEND, TxType.FEE},
    ProductType.FUND_PORTFOLIO: {TxType.FEE},
}

UNSIGNED_IMPORT_TX_FIELDS = (
    "amount",
    "fees",
    "retentions",
    "shares",
    "price",
    "currency_amount",
    "net_amount",
)


@dataclass
class TemplatedDataParserParams:
    template: Template
    number_format: NumberFormat
    feature: Feature
    product: ProductType
    datetime_format: Optional[str]
    date_format: Optional[str]
    params: dict[str, Any]


@dataclass
class ImportCandidate:
    name: Optional[str]
    source: DataSource
    params: TemplatedDataParserParams
    data: list[list[Any]]


@dataclass
class ImportFileRequest:
    file: FileUpload
    number_format: NumberFormat
    feature: Feature
    product: ProductType
    datetime_format: Optional[str]
    date_format: Optional[str]
    template: Optional[TemplateConfig] = None
    preview: bool = True
    template_fields: Optional[list[TemplatedField]] = None
    template_params: Optional[dict[str, Any]] = None


class ImportResultCode(str, Enum):
    # Success
    COMPLETED = "COMPLETED"

    # Failure
    UNSUPPORTED_FILE_FORMAT = "UNSUPPORTED_FILE_FORMAT"
    PDF_NO_TEXT_LAYER = "PDF_NO_TEXT_LAYER"
    NO_TABLE_FOUND = "NO_TABLE_FOUND"
    INVALID_TEMPLATE = "INVALID_TEMPLATE"

    # Import not configured
    DISABLED = "DISABLED"


class ImportErrorType(str, Enum):
    SHEET_NOT_FOUND = "SHEET_NOT_FOUND"
    MISSING_FIELD = "MISSING_FIELD"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNEXPECTED_COLUMN = "UNEXPECTED_COLUMN"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    DUPLICATED = "DUPLICATED"


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
class ImportRowOrigin:
    entry: Optional[str]
    row: list[str]


@dataclass
class TransactionsImportResult:
    transactions: Optional[Transactions]
    created_entities: set[Entity]
    errors: list[ImportError]
    origins: dict[UUID, ImportRowOrigin] = field(default_factory=dict)


@dataclass
class PositionImportResult:
    positions: list[GlobalPosition]
    created_entities: set[Entity]
    errors: list[ImportError]


@dataclass
class TemplateFieldsSuggestionRequest:
    file: FileUpload
    feature: Feature
    product: ProductType


@dataclass
class SuggestedTemplateField:
    field: str
    name: str


@dataclass
class TemplateFieldsSuggestion:
    headers: list[str]
    fields: list[SuggestedTemplateField]
    number_format: Optional[NumberFormat] = None
    date_format: Optional[str] = None
    detected_currency: Optional[str] = None
    missing_required_fields: list[str] = field(default_factory=list)
    matching_templates: list[UUID] = field(default_factory=list)


def resolve_account_tx_type(
    tx_type: Optional[TxType], amount: Dezimal
) -> Optional[TxType]:
    if tx_type in (TxType.FEE, TxType.INTEREST):
        return tx_type
    if amount < 0:
        return TxType.OUTFLOW
    if tx_type is not None:
        return tx_type
    if amount > 0:
        return TxType.INFLOW
    return None


def to_unsigned_tx_values(values: dict[str, Any]):
    for field_name in UNSIGNED_IMPORT_TX_FIELDS:
        value = values.get(field_name)
        if value is not None:
            values[field_name] = abs(value)


def tx_ref_key(tx: BaseTx) -> TxRefKey:
    return tx.entity.id, tx.product_type, tx.ref


def stored_entity_ids(result: TransactionsImportResult) -> list[UUID]:
    transactions = result.transactions or Transactions()
    created_ids = {entity.id for entity in result.created_entities}
    entity_ids = {
        tx.entity.id
        for tx in (transactions.investment or []) + (transactions.account or [])
    }
    return list(entity_ids - created_ids)


def exclude_duplicated_txs(
    result: TransactionsImportResult, existing_keys: set[TxRefKey]
) -> tuple[Transactions, list[ImportError]]:
    seen = set(existing_keys)
    errors = []

    def keep_unique(txs: Optional[list[BaseTx]]) -> list[BaseTx]:
        kept = []
        for tx in txs or []:
            key = tx_ref_key(tx)
            if key not in seen:
                seen.add(key)
                kept.append(tx)
                continue

            origin = result.origins.get(tx.id)
            errors.append(
                ImportError(
                    type=ImportErrorType.DUPLICATED,
                    entry=(origin.entry if origin else None) or "",
                    detail=[{"field": "ref", "value": tx.ref}],
                    row=origin.row if origin else None,
                )
            )
        return kept

    transactions = result.transactions or Transactions()
    unique = Transactions(
        investment=keep_unique(transactions.investment),
        account=keep_unique(transactions.account),
    )
    return unique, errors
