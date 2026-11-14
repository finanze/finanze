import hashlib
import logging
from datetime import date, datetime, time
from typing import Any, Optional
from uuid import UUID, uuid4

from application.ports.template_parser_port import TemplateParserPort
from dateutil.tz import tzlocal
from domain.currency_symbols import CURRENCY_SYMBOL_MAP
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.entity import Feature
from domain.exception.exceptions import MissingFieldsError
from domain.export import NumberFormat
from domain.global_position import (
    Account,
    Accounts,
    Card,
    Cards,
    CryptoCurrencies,
    CryptoCurrencyWallet,
    Deposit,
    Deposits,
    FactoringDetail,
    FactoringInvestments,
    FundDetail,
    FundInvestments,
    FundPortfolio,
    FundPortfolios,
    GlobalPosition,
    Loan,
    Loans,
    ProductPosition,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
    StockDetail,
    StockInvestments,
)
from domain.importing import (
    IMPORT_TX_TYPES_BY_PRODUCT,
    ImportCandidate,
    ImportError,
    ImportErrorType,
    ImportRowOrigin,
    PositionImportResult,
    TemplatedDataParserParams,
    TemplateFieldsSuggestion,
    TransactionsImportResult,
    resolve_account_tx_type,
    to_unsigned_tx_values,
)
from domain.template import EffectiveTemplatedField, Template, get_effective_field
from domain.template_fields import (
    ENTITY,
    PORTFOLIO_NAME,
    TEMPLATE_FIELD_MATRIX,
    TemplateField,
    TemplateFieldType,
)
from domain.template_header_aliases import normalize_header
from domain.transactions import (
    MAX_COUNTERPARTY_LENGTH,
    AccountTx,
    BaseTx,
    CryptoCurrencyTx,
    DepositTx,
    FactoringTx,
    FundPortfolioTx,
    FundTx,
    RealEstateCFTx,
    StockTx,
    Transactions,
    TxType,
    compute_net_amount,
    is_valid_iban_format,
    normalize_iban,
)
from infrastructure.templating.cell_values import (
    ISO_DATE_PATTERN,
    cell_text,
    detect_date_pattern,
    display_row,
    infer_number_format,
    is_empty_cell,
    parse_datetime,
    parse_number,
    parse_with_date_pattern,
)
from infrastructure.templating.field_suggestions import (
    HEADER_SCAN_ROWS,
    suggest_template_fields,
)
from pydantic import ValidationError


class InvalidFieldError(Exception):
    def __init__(self, field_name: str, value: str):
        self.field_name = field_name
        self.value = value
        message = f"Invalid field value: {field_name} = {value}"
        super().__init__(message)


_PRICE_QUANTITY_FIELDS = {
    ProductType.STOCK_ETF: "shares",
    ProductType.FUND: "shares",
    ProductType.CRYPTO: "currency_amount",
}


def _parse_temporal(
    value: Any,
    field: EffectiveTemplatedField,
    date_pattern: Optional[str],
    formats: tuple[Optional[str], Optional[str]],
) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time())

    text = cell_text(value).strip()
    if date_pattern is not None:
        try:
            return parse_with_date_pattern(text, date_pattern)
        except ValueError as e:
            raise InvalidFieldError(field.field, text) from e

    for date_format in formats:
        try:
            return parse_datetime(text, date_format)
        except ValueError:
            continue
    raise InvalidFieldError(field.field, text)


def _parse_cell(
    value: Any,
    params: TemplatedDataParserParams,
    field: EffectiveTemplatedField,
    number_format: NumberFormat,
    date_pattern: Optional[str],
) -> Any:
    field_type = field.type
    datetime_format = params.datetime_format or None
    date_format = params.date_format or None
    if field_type in (TemplateFieldType.DECIMAL, TemplateFieldType.INTEGER):
        try:
            return parse_number(value, number_format)
        except ValueError as e:
            raise InvalidFieldError(field.field, cell_text(value)) from e

    elif field_type == TemplateFieldType.DATETIME:
        parsed = _parse_temporal(
            value, field, date_pattern, (datetime_format, date_format)
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tzlocal())
        return parsed

    elif field_type == TemplateFieldType.DATE:
        return _parse_temporal(
            value, field, date_pattern, (date_format, datetime_format)
        ).date()

    elif field_type == TemplateFieldType.ENUM:
        enum_str = (value if isinstance(value, str) else cell_text(value)).strip()
        enum_str = enum_str.upper()
        if field.values and enum_str not in field.values:
            raise InvalidFieldError(field.field, cell_text(value))
        return enum_str

    elif field_type == TemplateFieldType.CURRENCY:
        currency_str = cell_text(value).strip().upper()
        if currency_str not in CURRENCY_SYMBOL_MAP:
            raise InvalidFieldError(field.field, cell_text(value))

        return currency_str

    elif field_type == TemplateFieldType.BOOLEAN:
        if isinstance(value, bool):
            return value
        lowered = cell_text(value).strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        elif lowered in ("false", "0", "no"):
            return False
        else:
            raise InvalidFieldError(field.field, cell_text(value))

    if isinstance(value, str):
        return " ".join(value.split())
    return cell_text(value)


def _has_header_constraints(template_fields: list[EffectiveTemplatedField]) -> bool:
    for field in template_fields:
        if (field.required or field.or_requires) and field.default_value is None:
            if normalize_header(field.name):
                return True
    return False


def _headers_satisfy_template(
    row_headers: set[str], template_fields: list[EffectiveTemplatedField]
) -> bool:
    for field in template_fields:
        if field.required and field.default_value is None:
            header = normalize_header(field.name)
            if header and header not in row_headers:
                return False

    by_field = {field.field: field for field in template_fields}
    checked_groups: set[frozenset[str]] = set()
    for field in template_fields:
        if not field.or_requires:
            continue
        group = frozenset([field.field, *field.or_requires])
        if group in checked_groups:
            continue
        checked_groups.add(group)
        present_members = [by_field[name] for name in group if name in by_field]
        if any(member.default_value is not None for member in present_members):
            continue
        member_headers = {
            normalize_header(member.name)
            for member in present_members
            if normalize_header(member.name)
        }
        if member_headers and not (member_headers & row_headers):
            return False
    return True


def _find_header_row(
    table: list[list[Any]], template_fields: list[EffectiveTemplatedField]
) -> Optional[int]:
    has_constraints = _has_header_constraints(template_fields)

    first_row_index = None
    for index, row in enumerate(table):
        if index >= HEADER_SCAN_ROWS and first_row_index is not None:
            break
        if all(is_empty_cell(value) for value in row):
            continue
        if first_row_index is None:
            first_row_index = index
        if not has_constraints:
            break
        row_headers = {normalize_header(cell_text(value)) for value in row}
        if _headers_satisfy_template(row_headers, template_fields):
            return index
    return first_row_index


def _template_match_score(
    table: list[list[Any]], template: Template
) -> Optional[tuple[int, int]]:
    template_fields = [
        get_effective_field(
            field.field, field.name or field.field, field.default_value, template
        )
        for field in template.fields
    ]
    template_fields = [field for field in template_fields if field is not None]
    header_index = _find_header_row(table, template_fields)
    if header_index is None:
        return None

    row_headers = {normalize_header(cell_text(value)) for value in table[header_index]}
    if not _headers_satisfy_template(row_headers, template_fields):
        return None

    names = {normalize_header(field.name) for field in template_fields}
    names.discard("")
    present = len(names & row_headers)
    if not present:
        return None
    return present, len(names) - present


def _generated_ref(
    product: ProductType, row: list[Any], occurrences: dict[str, int]
) -> str:
    cells = [" ".join(cell_text(value).split()) for value in row]
    while cells and not cells[-1]:
        cells.pop()
    digest = hashlib.sha256(
        "\x1f".join([product.value, *cells]).encode("utf-8")
    ).hexdigest()[:32]
    occurrence = occurrences.get(digest, 0)
    occurrences[digest] = occurrence + 1
    return digest if occurrence == 0 else f"{digest}-{occurrence}"


def _derive_price(tx_dict: dict, quantity_field: str) -> Dezimal:
    amount = tx_dict.get("amount")
    quantity = tx_dict.get(quantity_field)
    if amount is None or quantity is None or quantity == 0:
        raise MissingFieldsError(["price"])
    return abs(amount) / abs(quantity)


def _normalize_tx_text_fields(product: ProductType, tx_dict: dict):
    if "iban" in tx_dict:
        raw_iban = tx_dict["iban"]
        iban = normalize_iban(raw_iban)
        if iban is not None and not is_valid_iban_format(iban):
            raise InvalidFieldError("iban", str(raw_iban))
        tx_dict["iban"] = iban

    if "counterparty" in tx_dict:
        raw_counterparty = tx_dict["counterparty"]
        counterparty = raw_counterparty.strip() if raw_counterparty else None
        if counterparty and len(counterparty) > MAX_COUNTERPARTY_LENGTH:
            raise InvalidFieldError("counterparty", raw_counterparty)
        tx_dict["counterparty"] = counterparty or None

    if product == ProductType.CRYPTO and tx_dict.get("symbol") is not None:
        symbol = tx_dict["symbol"].strip().upper()
        if not symbol:
            raise MissingFieldsError(["symbol"])
        tx_dict["symbol"] = symbol


class TemplateDataParser(TemplateParserPort):
    PRODUCT_TYPE_CLS_MAP = {
        ProductType.ACCOUNT: (Accounts, Account),
        ProductType.CARD: (Cards, Card),
        ProductType.LOAN: (Loans, Loan),
        ProductType.DEPOSIT: (Deposits, Deposit),
        ProductType.FUND: (FundInvestments, FundDetail),
        ProductType.STOCK_ETF: (StockInvestments, StockDetail),
        ProductType.FACTORING: (FactoringInvestments, FactoringDetail),
        ProductType.REAL_ESTATE_CF: (RealEstateCFInvestments, RealEstateCFDetail),
        ProductType.CRYPTO: (CryptoCurrencies, CryptoCurrencyWallet),
    }

    TX_PROD_TYPE_ATTR_MAP = {
        ProductType.ACCOUNT: AccountTx,
        ProductType.STOCK_ETF: StockTx,
        ProductType.FUND: FundTx,
        ProductType.FUND_PORTFOLIO: FundPortfolioTx,
        ProductType.CRYPTO: CryptoCurrencyTx,
        ProductType.REAL_ESTATE_CF: RealEstateCFTx,
        ProductType.FACTORING: FactoringTx,
        ProductType.DEPOSIT: DepositTx,
    }

    def __init__(self):
        self._log = logging.getLogger(__name__)

    async def global_positions(
        self, candidates: list[ImportCandidate], existing_entities: dict[str, Entity]
    ) -> PositionImportResult:
        all_errors = []
        global_positions_dicts = {}

        for candidate in candidates:
            last_candidate = candidate
            product_type = candidate.params.product

            per_entity, errors = self._load_products(product_type, candidate)
            all_errors.extend(errors)
            for entity in per_entity:
                if entity not in global_positions_dicts:
                    global_positions_dicts[entity] = {"products": {}}

                if product_type in global_positions_dicts[entity]["products"]:
                    global_positions_dicts[entity]["products"][product_type] += (
                        per_entity[entity]
                    )
                else:
                    global_positions_dicts[entity]["products"][product_type] = (
                        per_entity[entity]
                    )

        for entity, positions in global_positions_dicts.items():
            required_portfolios = {}
            if (
                ProductType.FUND in positions["products"]
                and positions["products"][ProductType.FUND]
            ):
                for fund in positions["products"][ProductType.FUND].entries:
                    if fund.portfolio:
                        if fund.portfolio.name not in required_portfolios:
                            fund.portfolio.currency = fund.currency
                            required_portfolios[fund.portfolio.name] = fund.portfolio
                        else:
                            fund.portfolio = required_portfolios[fund.portfolio.name]

            if required_portfolios:
                positions["products"][ProductType.FUND_PORTFOLIO] = FundPortfolios(
                    list(required_portfolios.values())
                )

        created_entities = {}
        global_positions = []
        for entity, data in global_positions_dicts.items():
            if entity in existing_entities:
                entity = existing_entities[entity]
            else:
                if entity not in created_entities:
                    created_entities[entity] = Entity(
                        id=uuid4(),
                        name=entity,
                        natural_id=None,
                        type=EntityType.FINANCIAL_INSTITUTION,
                        origin=EntityOrigin.MANUAL,
                        icon_url=None,
                    )
                entity = created_entities[entity]

            products = data["products"]
            global_positions.append(
                GlobalPosition(
                    id=uuid4(),
                    entity=entity,
                    products=products,
                    source=last_candidate.source,
                )
            )

        return PositionImportResult(
            global_positions, set(created_entities.values()), all_errors
        )

    def _load_products(
        self,
        product_type,
        candidate: ImportCandidate,
    ) -> tuple[dict[str, ProductPosition], list[ImportError]]:
        parent_cls, cls = self.PRODUCT_TYPE_CLS_MAP.get(product_type, (None, None))

        if not parent_cls and not cls:
            raise InvalidFieldError(
                "product_type",
                product_type,
            )

        details_per_entity = {}

        def process_entry_fn(row, product_dict):
            p_id = uuid4()
            product_dict["id"] = p_id
            product_dict["source"] = candidate.source

            entity = product_dict.get(ENTITY.field) or candidate.params.params.get(
                "entity"
            )
            if not entity:
                raise MissingFieldsError(["entity"])

            entity_products = details_per_entity.get(entity, [])

            if cls == FundDetail:
                portfolio_name = product_dict.get(PORTFOLIO_NAME.field)
                if portfolio_name:
                    product_dict["portfolio"] = FundPortfolio(
                        id=uuid4(),
                        name=portfolio_name,
                        initial_investment=Dezimal(0),
                        market_value=Dezimal(0),
                        source=candidate.source,
                    )

            entity_products.append(cls.from_dict(product_dict))

            details_per_entity[entity] = entity_products

        errors = self._parse_sheet_table(candidate, process_entry_fn)

        if not details_per_entity:
            return {}, errors

        per_entity = {}
        for entity, entity_products in details_per_entity.items():
            if parent_cls is None:
                per_entity[entity] = (
                    entity_products[0] if len(entity_products) == 1 else {}
                )
            else:
                parent_obj_dict = {
                    "entries": entity_products,
                }

                per_entity[entity] = parent_cls(**parent_obj_dict)

        return per_entity, errors

    async def transactions(
        self, candidates: list[ImportCandidate], existing_entities: dict[str, Entity]
    ) -> TransactionsImportResult:
        all_errors = []
        all_created_entities = {}
        all_origins = {}
        transactions = Transactions(investment=[], account=[])

        for candidate in candidates:
            txs, created_entities, origins, errors = self._load_txs(
                candidate, existing_entities, all_created_entities
            )
            all_errors.extend(errors)
            all_created_entities.update(created_entities)
            all_origins.update(origins)

            if candidate.params.product == ProductType.ACCOUNT:
                current_transactions = Transactions(account=txs)
            else:
                current_transactions = Transactions(investment=txs)

            if current_transactions:
                transactions += current_transactions

        return TransactionsImportResult(
            transactions,
            set(all_created_entities.values()),
            all_errors,
            all_origins,
        )

    async def suggest_fields(
        self,
        table: list[list[Any]],
        fields: list[TemplateField],
        templates: list[Template],
    ) -> TemplateFieldsSuggestion:
        suggestion = suggest_template_fields(table, fields)
        scored = []
        for template in templates:
            score = _template_match_score(table, template)
            if score is not None:
                scored.append((score, template.id))
        scored.sort(key=lambda item: (-item[0][0], item[0][1]))
        suggestion.matching_templates = [template_id for _, template_id in scored]
        return suggestion

    def _load_txs(
        self,
        candidate: ImportCandidate,
        existing_entities: dict[str, Entity],
        already_created_entities: dict[str, Entity],
    ) -> tuple[
        list[BaseTx],
        dict[str, Entity],
        dict[UUID, ImportRowOrigin],
        list[ImportError],
    ]:
        txs = []
        created_entities = {}
        origins = {}
        prod_type = candidate.params.product
        allowed_types = IMPORT_TX_TYPES_BY_PRODUCT.get(prod_type)
        product_defaults = {
            field.field: field.default_value
            for field in TEMPLATE_FIELD_MATRIX[Feature.TRANSACTIONS].get(prod_type, [])
            if field.default_value is not None
        }
        ref_occurrences: dict[str, int] = {}

        def process_entry_fn(row, tx_dict):
            if prod_type not in self.TX_PROD_TYPE_ATTR_MAP:
                raise InvalidFieldError(
                    "product_type",
                    prod_type,
                )

            tx_type = tx_dict.get("type")
            if (
                allowed_types is not None
                and tx_type
                and TxType(tx_type) not in allowed_types
            ):
                raise InvalidFieldError("type", tx_type)

            if not tx_dict.get("name"):
                fallback_name = tx_dict.get("isin") or tx_dict.get("ticker")
                if not fallback_name:
                    raise MissingFieldsError(["name"])
                tx_dict["name"] = fallback_name

            if not tx_dict.get("ref"):
                tx_dict["ref"] = _generated_ref(prod_type, row, ref_occurrences)

            for field_name, default_value in product_defaults.items():
                if tx_dict.get(field_name) is None:
                    tx_dict[field_name] = default_value

            tx_id = uuid4()
            tx_dict["id"] = tx_id
            tx_dict["source"] = candidate.source

            amount_in = tx_dict.pop("amount_in", None)
            amount_out = tx_dict.pop("amount_out", None)
            if tx_dict.get("amount") is None and (
                amount_in is not None or amount_out is not None
            ):
                inflow = abs(amount_in) if amount_in is not None else Dezimal(0)
                outflow = abs(amount_out) if amount_out is not None else Dezimal(0)
                tx_dict["amount"] = inflow - outflow

            if tx_type == TxType.SPLIT.value:
                for field in ("amount", "price"):
                    if tx_dict.get(field) is None:
                        tx_dict[field] = Dezimal(0)
                ratio = tx_dict.get("split_ratio")
                if ratio is None or not ratio.val.is_finite() or ratio <= 0:
                    raise InvalidFieldError("split_ratio", str(ratio))
                amount = tx_dict["amount"]
                price = tx_dict["price"]
                if amount < 0:
                    raise InvalidFieldError("amount", str(amount))
                if price < 0:
                    raise InvalidFieldError("price", str(price))
                for field in ("fees", "retentions", "shares"):
                    value = tx_dict.get(field)
                    if value is not None and value < 0:
                        raise InvalidFieldError(field, str(value))
                if amount > 0 and price <= 0:
                    raise InvalidFieldError("price", str(price))
                if prod_type == ProductType.FUND and not tx_dict.get("isin"):
                    raise MissingFieldsError(["isin"])
                if prod_type == ProductType.STOCK_ETF and not (
                    tx_dict.get("isin") or tx_dict.get("ticker")
                ):
                    raise MissingFieldsError(["isin", "ticker"])
            else:
                if prod_type == ProductType.ACCOUNT:
                    amount = tx_dict.get("amount")
                    if amount is None:
                        raise MissingFieldsError(["amount"])
                    resolved_type = resolve_account_tx_type(
                        TxType(tx_type) if tx_type else None, amount
                    )
                    if resolved_type is None:
                        raise MissingFieldsError(["type"])
                    tx_dict["type"] = resolved_type
                quantity_field = _PRICE_QUANTITY_FIELDS.get(prod_type)
                if quantity_field and tx_dict.get("price") is None:
                    tx_dict["price"] = _derive_price(tx_dict, quantity_field)
                to_unsigned_tx_values(tx_dict)

            _normalize_tx_text_fields(prod_type, tx_dict)

            entity_name = tx_dict.get(ENTITY.field) or candidate.params.params.get(
                "entity"
            )
            if not entity_name:
                raise MissingFieldsError(["entity"])

            if entity_name in existing_entities:
                tx_dict["entity"] = existing_entities[entity_name]

            elif entity_name in already_created_entities:
                tx_dict["entity"] = already_created_entities[entity_name]

            else:
                if entity_name not in created_entities:
                    created_entities[entity_name] = Entity(
                        id=uuid4(),
                        name=entity_name,
                        natural_id=None,
                        type=EntityType.FINANCIAL_INSTITUTION,
                        origin=EntityOrigin.MANUAL,
                        icon_url=None,
                    )

                tx_dict["entity"] = created_entities[entity_name]

            cls = self.TX_PROD_TYPE_ATTR_MAP[prod_type]
            tx_dict["product_type"] = prod_type
            tx = cls.from_dict(tx_dict)
            if hasattr(tx, "net_amount") and tx.net_amount is None:
                tx.net_amount = compute_net_amount(tx)
            txs.append(tx)
            origins[tx_id] = ImportRowOrigin(entry=candidate.name, row=display_row(row))

        errors = self._parse_sheet_table(candidate, process_entry_fn)

        return txs, created_entities, origins, errors

    def _parse_sheet_table(
        self, candidate: ImportCandidate, entry_fn
    ) -> list[ImportError]:
        table = candidate.data
        config = candidate.params
        errors = []
        template_fields = [
            get_effective_field(
                field.field,
                field.name or field.field,
                field.default_value,
                config.template,
            )
            for field in config.template.fields
        ]
        template_fields = [field for field in template_fields if field is not None]

        header_row_index = _find_header_row(table, template_fields)
        if header_row_index is None:
            return errors

        header_row = table[header_row_index]
        start_column_index = next(
            index for index, value in enumerate(header_row) if not is_empty_cell(value)
        )

        fields_by_header = {}
        for field in template_fields:
            fields_by_header.setdefault(normalize_header(field.name), field)

        columns = []
        unexpected_columns = []
        mapped_fields = set()
        for column in header_row[start_column_index:]:
            header = normalize_header(cell_text(column))
            templated_field = fields_by_header.get(header) if header else None
            if templated_field is not None and templated_field.field in mapped_fields:
                templated_field = None
            if templated_field is None:
                if header:
                    unexpected_columns.append(cell_text(column).strip())
            else:
                mapped_fields.add(templated_field.field)

            columns.append(templated_field)

        columns.extend(
            field for field in template_fields if field.field not in mapped_fields
        )

        if unexpected_columns:
            errors.append(
                ImportError(
                    ImportErrorType.UNEXPECTED_COLUMN,
                    candidate.name,
                    unexpected_columns,
                )
            )

        indexed_columns = [
            (j, column)
            for j, column in enumerate(columns, start_column_index)
            if column is not None
        ]
        data_rows = [
            row
            for row in table[header_row_index + 1 :]
            if any(
                j < len(row) and not is_empty_cell(row[j]) for j, _ in indexed_columns
            )
        ]

        auto_dates = not (config.date_format or config.datetime_format)
        number_formats = {}
        date_patterns = {}
        for j, column in indexed_columns:
            values = [row[j] for row in data_rows if j < len(row)]
            if column.type in (TemplateFieldType.DECIMAL, TemplateFieldType.INTEGER):
                number_formats[j] = infer_number_format(values) or config.number_format
            elif auto_dates and column.type in (
                TemplateFieldType.DATE,
                TemplateFieldType.DATETIME,
            ):
                date_patterns[j] = detect_date_pattern(values) or ISO_DATE_PATTERN

        transaction_type_column = next(
            (j for j, column in indexed_columns if column.field == "type"),
            None,
        )

        for raw_row in data_rows:
            row = display_row(raw_row)
            raw_parsed_row = {}
            missing_fields = []
            invalid_fields = []
            row_type = (
                row[transaction_type_column].strip().upper()
                if transaction_type_column is not None
                and transaction_type_column < len(row)
                else ""
            )
            is_split_row = (
                config.feature == Feature.TRANSACTIONS
                and config.product in {ProductType.STOCK_ETF, ProductType.FUND}
                and row_type == TxType.SPLIT.value
            )
            for j, column in indexed_columns:
                value = raw_row[j] if j < len(raw_row) else None
                if is_empty_cell(value):
                    if is_split_row and column.field in {"amount", "price"}:
                        value = Dezimal(0)
                    elif is_split_row and column.field == "shares":
                        value = None
                    else:
                        value = column.default_value
                    required = column.required and not (
                        is_split_row and column.field in {"amount", "price", "shares"}
                    )
                    required = required or (
                        is_split_row and column.field == "split_ratio"
                    )
                    if value is None and required:
                        missing_fields.append(column.field)
                        continue

                try:
                    parsed = None
                    if value is not None:
                        parsed = _parse_cell(
                            value,
                            config,
                            column,
                            number_formats.get(j, config.number_format),
                            date_patterns.get(j),
                        )
                except InvalidFieldError as e:
                    invalid_fields.append({"field": e.field_name, "value": e.value})
                    continue

                raw_parsed_row[column.field] = parsed

            if (
                config.feature == Feature.TRANSACTIONS
                and config.product == ProductType.ACCOUNT
                and not is_split_row
                and any(
                    col.field in {"amount", "amount_in", "amount_out"}
                    for _, col in indexed_columns
                )
            ):
                invalid_names = {item["field"] for item in invalid_fields}
                if not (invalid_names & {"amount", "amount_in", "amount_out"}) and all(
                    raw_parsed_row.get(k) is None
                    for k in ("amount", "amount_in", "amount_out")
                ):
                    if "amount" not in missing_fields:
                        missing_fields.append("amount")

            if invalid_fields:
                errors.append(
                    ImportError(
                        ImportErrorType.VALIDATION_ERROR,
                        candidate.name,
                        invalid_fields,
                        row,
                    )
                )

            if missing_fields:
                errors.append(
                    ImportError(
                        ImportErrorType.MISSING_FIELD,
                        candidate.name,
                        [{"field": field} for field in missing_fields],
                        row,
                    )
                )

            if invalid_fields or missing_fields:
                continue

            try:
                entry_fn(raw_row, raw_parsed_row)
            except MissingFieldsError as e:
                errors.append(
                    ImportError(
                        ImportErrorType.MISSING_FIELD,
                        candidate.name,
                        e.missing_fields,
                        row,
                    )
                )
                self._log.warning(f"Skipping row {row}: {e}")
                continue
            except ValidationError as e:
                errors.append(
                    ImportError(
                        ImportErrorType.VALIDATION_ERROR,
                        candidate.name,
                        [
                            {
                                "field": ".".join(map(str, error.get("loc"))),
                                "value": error.get("input"),
                            }
                            for error in e.errors()
                        ],
                        row,
                    )
                )
                self._log.warning(f"Skipping row {row}: {e}")
                continue
            except InvalidFieldError as e:
                errors.append(
                    ImportError(
                        ImportErrorType.VALIDATION_ERROR,
                        candidate.name,
                        [
                            {
                                "field": e.field_name,
                                "value": e.value,
                            }
                        ],
                        row,
                    )
                )
                self._log.warning(f"Skipping row {row}: {e}")
                continue
            except Exception as e:
                errors.append(
                    ImportError(
                        ImportErrorType.UNEXPECTED_ERROR,
                        candidate.name,
                        [str(e)],
                        row,
                    )
                )
                self._log.warning(f"Skipping row {row}: {e}")
                continue
        return errors
