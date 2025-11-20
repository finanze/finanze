import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from application.ports.template_parser_port import TemplateParserPort
from domain.currency_symbols import CURRENCY_SYMBOL_MAP
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import MissingFieldsError
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
    ImportCandidate,
    ImportError,
    ImportErrorType,
    PositionImportResult,
    TemplatedDataParserParams,
    TransactionsImportResult,
)
from domain.template import EffectiveTemplatedField, get_effective_field
from domain.template_fields import ENTITY, TemplateFieldType, PORTFOLIO_NAME
from domain.transactions import (
    BaseTx,
    DepositTx,
    FactoringTx,
    FundTx,
    RealEstateCFTx,
    StockTx,
    Transactions,
)
from pydantic import ValidationError


class InvalidFieldError(Exception):
    def __init__(self, field_name: str, value: str):
        self.field_name = field_name
        self.value = value
        message = f"Invalid field value: {field_name} = {value}"
        super().__init__(message)


def parse_number(value: Any) -> Dezimal:
    value = (
        value.strip().replace(".", "").replace(",", ".")
        if isinstance(value, str)
        else value
    )
    return Dezimal(value)


def _parse_cell(
    value: str, params: TemplatedDataParserParams, field: EffectiveTemplatedField
) -> Any:
    field_type = field.type
    if field_type in (TemplateFieldType.DECIMAL, TemplateFieldType.INTEGER):
        return parse_number(value)

    elif field_type == TemplateFieldType.DATETIME:
        try:
            return datetime.strptime(value, params.datetime_format)
        except ValueError:
            try:
                return datetime.strptime(value, params.date_format)
            except ValueError:
                pass
            raise InvalidFieldError(field.field, value)

    elif field_type == TemplateFieldType.DATE:
        try:
            return datetime.strptime(value, params.date_format).date()
        except ValueError:
            try:
                return datetime.strptime(value, params.datetime_format).date()
            except ValueError:
                pass
            raise InvalidFieldError(field.field, value)

    elif field_type == TemplateFieldType.ENUM:
        enum_str = value.upper()
        if field.values and enum_str not in field.values:
            raise InvalidFieldError(field.field, value)
        return enum_str

    elif field_type == TemplateFieldType.CURRENCY:
        currency_str = str(value).upper()
        if currency_str not in CURRENCY_SYMBOL_MAP:
            raise InvalidFieldError(field.field, value)

        return currency_str

    elif field_type == TemplateFieldType.BOOLEAN:
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        elif lowered in ("false", "0", "no"):
            return False
        else:
            raise InvalidFieldError(field.field, value)

    return value


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
        ProductType.STOCK_ETF: StockTx,
        ProductType.FUND: FundTx,
        ProductType.REAL_ESTATE_CF: RealEstateCFTx,
        ProductType.FACTORING: FactoringTx,
        ProductType.DEPOSIT: DepositTx,
    }

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def global_positions(
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

    def transactions(
        self, candidates: list[ImportCandidate], existing_entities: dict[str, Entity]
    ) -> TransactionsImportResult:
        all_errors = []
        all_created_entities = {}
        transactions = Transactions(investment=[], account=[])

        for candidate in candidates:
            txs, created_entities, errors = self._load_txs(
                candidate, existing_entities, all_created_entities
            )
            all_errors.extend(errors)
            all_created_entities.update(created_entities)

            if candidate.params.product == ProductType.ACCOUNT:
                current_transactions = Transactions(account=txs)
            else:
                current_transactions = Transactions(investment=txs)

            if current_transactions:
                transactions += current_transactions

        return TransactionsImportResult(
            transactions, set(all_created_entities.values()), all_errors
        )

    def _load_txs(
        self,
        candidate: ImportCandidate,
        existing_entities: dict[str, Entity],
        already_created_entities: dict[str, Entity],
    ) -> tuple[list[BaseTx], dict[str, Entity], list[ImportError]]:
        txs = []
        created_entities = {}
        prod_type = candidate.params.product

        def process_entry_fn(row, tx_dict):
            tx_id = uuid4()
            tx_dict["id"] = tx_id
            tx_dict["source"] = candidate.source

            if prod_type not in self.TX_PROD_TYPE_ATTR_MAP:
                raise InvalidFieldError(
                    "product_type",
                    prod_type,
                )

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
                    )

                tx_dict["entity"] = created_entities[entity_name]

            cls = self.TX_PROD_TYPE_ATTR_MAP[prod_type]
            tx_dict["product_type"] = prod_type
            txs.append(cls.from_dict(tx_dict))

        errors = self._parse_sheet_table(candidate, process_entry_fn)

        return txs, created_entities, errors

    def _parse_sheet_table(
        self, candidate: ImportCandidate, entry_fn
    ) -> list[ImportError]:
        table = candidate.data
        config = candidate.params
        errors = []
        header_row_index, start_column_index = next(
            (
                (index, next((i for i, x in enumerate(row) if x), None))
                for index, row in enumerate(table)
                if row
            ),
            (None, None),
        )
        if header_row_index is None or start_column_index is None:
            return errors

        raw_columns = table[header_row_index][start_column_index:]
        template_fields = [
            get_effective_field(
                field.field,
                field.name or field.field,
                field.default_value,
                config.template,
            )
            for field in config.template.fields
        ]

        columns = []
        unexpected_columns = []
        for column in raw_columns:
            templated_field = next(
                (f for f in template_fields if f.name == column),
                None,
            )
            if not templated_field:
                unexpected_columns.append(column)

            columns.append(templated_field)

        missing_columns = [field for field in template_fields if field not in columns]
        columns.extend(missing_columns)

        if unexpected_columns:
            errors.append(
                ImportError(
                    ImportErrorType.UNEXPECTED_COLUMN,
                    candidate.name,
                    unexpected_columns,
                )
            )

        for row in table[header_row_index + 1 :]:
            raw_parsed_row = {}
            missing_fields = []
            for j, column in enumerate(columns, start_column_index):
                if not column:
                    continue

                value = row[j] if j < len(row) else None
                if not value:
                    value = column.default_value
                    if value is None and column.required:
                        missing_fields.append(column.field)
                        continue

                try:
                    parsed = None
                    if value is not None:
                        parsed = _parse_cell(value, config, column)
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
                    continue

                raw_parsed_row[column.field] = parsed

            if missing_fields:
                errors.append(
                    ImportError(
                        ImportErrorType.MISSING_FIELD,
                        candidate.name,
                        [{"field": field} for field in missing_fields],
                        row,
                    )
                )
                continue

            try:
                entry_fn(row, raw_parsed_row)
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
