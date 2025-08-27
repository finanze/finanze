import json
import logging
from datetime import datetime
from uuid import uuid4

from application.ports.virtual_fetch import VirtualFetcher
from domain.entity import Entity, EntityType
from domain.exception.exceptions import MissingFieldsError
from domain.global_position import (
    Account,
    Accounts,
    Card,
    Cards,
    Commodities,
    Commodity,
    Crowdlending,
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
from domain.settings import (
    BaseSheetConfig,
    GoogleCredentials,
    VirtualPositionSheetConfig,
    VirtualTransactionSheetConfig,
)
from domain.transactions import (
    BaseTx,
    DepositTx,
    FactoringTx,
    FundTx,
    RealEstateCFTx,
    StockTx,
    Transactions,
)
from domain.virtual_fetch_result import (
    VirtualFetchError,
    VirtualFetchErrorType,
    VirtualPositionResult,
    VirtualTransactionResult,
)
from googleapiclient.errors import HttpError
from infrastructure.sheets.sheets_service_loader import SheetsServiceLoader
from pydantic import ValidationError

DEFAULT_DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"
DEFAULT_DATE_FORMAT = "%d/%m/%Y"


class InvalidFieldError(Exception):
    def __init__(self, field_name: str, value: str):
        self.field_name = field_name
        self.value = value
        message = f"Invalid field value: {field_name} = {value}"
        super().__init__(message)


def parse_number(value: str) -> float:
    return float(value.strip().replace(".", "").replace(",", "."))


def _parse_cell(value: str, config: BaseSheetConfig) -> any:
    try:
        return parse_number(value)
    except ValueError:
        try:
            datetime_format = config.datetimeFormat or DEFAULT_DATETIME_FORMAT
            return datetime.strptime(value, datetime_format)
        except ValueError:
            try:
                date_format = config.dateFormat or DEFAULT_DATE_FORMAT
                return datetime.strptime(value, date_format).date()
            except ValueError:
                if not len(value):
                    return None
                return value


class SheetsImporter(VirtualFetcher):
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
        ProductType.COMMODITY: (Commodities, Commodity),
        ProductType.CROWDLENDING: (None, Crowdlending),
    }

    TX_PROD_TYPE_ATTR_MAP = {
        "STOCK_ETF": StockTx,
        "FUND": FundTx,
        "REAL_ESTATE_CF": RealEstateCFTx,
        "FACTORING": FactoringTx,
        "DEPOSIT": DepositTx,
    }

    def __init__(self, sheets_service: SheetsServiceLoader):
        self._sheets_service = sheets_service
        self._log = logging.getLogger(__name__)

    async def global_positions(
        self,
        credentials: GoogleCredentials,
        position_configs: list[VirtualPositionSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> VirtualPositionResult:
        all_errors = []
        global_positions_dicts = {}
        for config in position_configs:
            field = config.data
            parent_type, detail_type = self.PRODUCT_TYPE_CLS_MAP.get(
                field, (None, None)
            )

            if not parent_type and not detail_type:
                raise InvalidFieldError(
                    "product_type",
                    field,
                )

            per_entity, errors = self._load_products(
                detail_type, parent_type, credentials, config
            )
            all_errors.extend(errors)
            for entity in per_entity:
                if entity not in global_positions_dicts:
                    global_positions_dicts[entity] = {"products": {}}

                if field in global_positions_dicts[entity]["products"]:
                    global_positions_dicts[entity]["products"][field] += per_entity[
                        entity
                    ]
                else:
                    global_positions_dicts[entity]["products"][field] = per_entity[
                        entity
                    ]

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

                        fund.portfolio.initial_investment = (
                            fund.portfolio.initial_investment or 0
                        ) + fund.initial_investment or 0
                        fund.portfolio.market_value = (
                            fund.portfolio.market_value or 0
                        ) + fund.market_value or 0

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
                        type=EntityType.FINANCIAL_INSTITUTION,
                        is_real=False,
                    )
                entity = created_entities[entity]

            products = data["products"]
            global_positions.append(
                GlobalPosition(
                    id=uuid4(), entity=entity, products=products, is_real=False
                )
            )

        return VirtualPositionResult(
            global_positions, set(created_entities.values()), all_errors
        )

    def _load_products(
        self,
        cls,
        parent_cls,
        credentials: GoogleCredentials,
        config: VirtualPositionSheetConfig,
    ) -> tuple[dict[str, ProductPosition], list[VirtualFetchError]]:
        details_per_entity = {}

        def process_entry_fn(row, product_dict):
            p_id = uuid4()
            product_dict["id"] = p_id
            if "entity" not in product_dict:
                raise MissingFieldsError(["entity"])

            entity = product_dict["entity"]
            entity_products = details_per_entity.get(entity, [])

            if cls == FundDetail:
                portfolio_name = product_dict.get("portfolio")
                if portfolio_name:
                    product_dict["portfolio"] = FundPortfolio(
                        id=uuid4(), name=portfolio_name
                    )
            elif cls == Crowdlending:
                product_dict["distribution"] = (
                    json.loads(product_dict["distribution"])
                    if product_dict.get("distribution")
                    else None
                )

            entity_products.append(cls.from_dict(product_dict))

            details_per_entity[entity] = entity_products

        errors = self._parse_sheet_table(credentials, config, process_entry_fn)

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
        self,
        credentials: GoogleCredentials,
        txs_configs: list[VirtualTransactionSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> VirtualTransactionResult:
        all_errors = []
        all_created_entities = {}
        transactions = Transactions(investment=[], account=[])

        for config in txs_configs:
            field = config.data

            txs, created_entities, errors = self._load_txs(
                credentials, config, existing_entities, all_created_entities
            )
            all_errors.extend(errors)
            all_created_entities.update(created_entities)

            current_transactions = None
            if field == "investment":
                current_transactions = Transactions(investment=txs)
            elif field == "account":
                current_transactions = Transactions(account=txs)

            if current_transactions:
                transactions += current_transactions

        return VirtualTransactionResult(
            transactions, set(all_created_entities.values()), all_errors
        )

    def _load_txs(
        self,
        credentials: GoogleCredentials,
        config: VirtualTransactionSheetConfig,
        existing_entities: dict[str, Entity],
        already_created_entities: dict[str, Entity],
    ) -> tuple[list[BaseTx], dict[str, Entity], list[VirtualFetchError]]:
        txs = []
        created_entities = {}

        def process_entry_fn(row, tx_dict):
            tx_id = uuid4()
            tx_dict["id"] = tx_id
            tx_dict["is_real"] = False

            if "product_type" not in tx_dict:
                raise MissingFieldsError(["product_type"])

            prod_type = tx_dict["product_type"]
            if prod_type not in self.TX_PROD_TYPE_ATTR_MAP:
                raise InvalidFieldError(
                    "product_type",
                    prod_type,
                )

            if "entity" not in tx_dict:
                raise MissingFieldsError(["entity"])

            entity_name = tx_dict["entity"]
            if entity_name in existing_entities:
                tx_dict["entity"] = existing_entities[entity_name]

            elif entity_name in already_created_entities:
                tx_dict["entity"] = already_created_entities[entity_name]

            else:
                if entity_name not in created_entities:
                    created_entities[entity_name] = Entity(
                        id=uuid4(),
                        name=entity_name,
                        type=EntityType.FINANCIAL_INSTITUTION,
                        is_real=False,
                    )

                tx_dict["entity"] = created_entities[entity_name]

            cls = self.TX_PROD_TYPE_ATTR_MAP[prod_type]
            txs.append(cls.from_dict(tx_dict))

        errors = self._parse_sheet_table(credentials, config, process_entry_fn)

        return txs, created_entities, errors

    def _parse_sheet_table(
        self, credentials: GoogleCredentials, config: BaseSheetConfig, entry_fn
    ) -> list[VirtualFetchError]:
        sheet_range, sheet_id = config.range, config.spreadsheetId
        cells, errors = self._read_sheet_table(credentials, sheet_id, sheet_range)
        if not cells:
            return errors

        header_row_index, start_column_index = next(
            (
                (index, next((i for i, x in enumerate(row) if x), None))
                for index, row in enumerate(cells)
                if row
            ),
            (None, None),
        )
        if header_row_index is None or start_column_index is None:
            return errors

        columns = cells[header_row_index][start_column_index:]

        for row in cells[header_row_index + 1 :]:
            entry_dict = {}
            for j, column in enumerate(columns, start_column_index):
                if not column or j >= len(row):
                    continue
                parsed = _parse_cell(row[j], config)
                if parsed is not None:
                    entry_dict[column] = parsed

            try:
                entry_fn(row, entry_dict)
            except MissingFieldsError as e:
                errors.append(
                    VirtualFetchError(
                        VirtualFetchErrorType.MISSING_FIELD,
                        config.range,
                        e.missing_fields,
                        row,
                    )
                )
                self._log.warning(f"Skipping row {row}: {e}")
                continue
            except ValidationError as e:
                errors.append(
                    VirtualFetchError(
                        VirtualFetchErrorType.VALIDATION_ERROR,
                        config.range,
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
                    VirtualFetchError(
                        VirtualFetchErrorType.VALIDATION_ERROR,
                        config.range,
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
                    VirtualFetchError(
                        VirtualFetchErrorType.UNEXPECTED_ERROR,
                        config.range,
                        [str(e)],
                        row,
                    )
                )
                self._log.warning(f"Skipping row {row}: {e}")
                continue
        return errors

    def _read_sheet_table(
        self, credentials: GoogleCredentials, sheet_id, cell_range
    ) -> tuple[list[list], list[VirtualFetchError]]:
        sheets_service = self._sheets_service.service(credentials)
        errors = []
        try:
            result = (
                sheets_service.values()
                .get(spreadsheetId=sheet_id, range=cell_range)
                .execute()
            )
        except HttpError as e:
            if e.status_code == 400:
                errors.append(
                    VirtualFetchError(VirtualFetchErrorType.SHEET_NOT_FOUND, cell_range)
                )
                self._log.warning(f"Sheet {sheet_id} not found")
                return [], errors
            else:
                raise

        return result.get("values", []), errors
