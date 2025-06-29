import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from application.ports.virtual_fetch import VirtualFetcher
from domain.entity import Entity, EntityType
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
    RealStateCFDetail,
    RealStateCFInvestments,
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
    FactoringTx,
    FundTx,
    RealStateCFTx,
    StockTx,
    Transactions,
)
from infrastructure.sheets.sheets_service_loader import SheetsServiceLoader
from pydantic import ValidationError

DEFAULT_DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"
DEFAULT_DATE_FORMAT = "%d/%m/%Y"


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
        ProductType.REAL_STATE_CF: (RealStateCFInvestments, RealStateCFDetail),
        ProductType.CRYPTO: (CryptoCurrencies, CryptoCurrencyWallet),
    }

    TX_PROD_TYPE_ATTR_MAP = {
        "STOCK_ETF": StockTx,
        "FUND": FundTx,
        "REAL_STATE_CF": RealStateCFTx,
        "FACTORING": FactoringTx,
    }

    def __init__(self, sheets_service: SheetsServiceLoader):
        self._sheets_service = sheets_service
        self._log = logging.getLogger(__name__)

    async def global_positions(
        self,
        credentials: GoogleCredentials,
        position_configs: list[VirtualPositionSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> tuple[list[GlobalPosition], set[Entity]]:
        global_positions_dicts = {}
        for config in position_configs:
            field = config.data
            parent_type, detail_type = self.PRODUCT_TYPE_CLS_MAP.get(
                field, (None, None)
            )
            if not parent_type:
                raise ValueError(f"Invalid field {field}")

            per_entity = self._load_products(
                detail_type, parent_type, credentials, config
            )
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

        return global_positions, set(created_entities.values())

    def _load_products(
        self,
        cls,
        parent_cls,
        credentials: GoogleCredentials,
        config: VirtualPositionSheetConfig,
    ) -> dict[str, ProductPosition]:
        details_per_entity = {}

        def process_entry_fn(row, product_dict):
            p_id = uuid4()
            product_dict["id"] = p_id
            entity = product_dict["entity"]
            entity_products = details_per_entity.get(entity, [])

            if cls == FundDetail:
                portfolio_name = product_dict.get("portfolio")
                if portfolio_name:
                    product_dict["portfolio"] = FundPortfolio(
                        id=uuid4(), name=portfolio_name
                    )

            entity_products.append(cls.from_dict(product_dict))

            details_per_entity[entity] = entity_products

        self._parse_sheet_table(credentials, config, process_entry_fn)

        if not details_per_entity:
            return {}

        per_entity = {}
        for entity, entity_products in details_per_entity.items():
            parent_obj_dict = {
                "entries": entity_products,
            }

            per_entity[entity] = parent_cls(**parent_obj_dict)

        return per_entity

    async def transactions(
        self,
        credentials: GoogleCredentials,
        txs_configs: list[VirtualTransactionSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> tuple[Optional[Transactions], set[Entity]]:
        all_created_entities = {}
        transactions = Transactions(investment=[], account=[])

        for config in txs_configs:
            field = config.data

            txs, created_entities = self._load_txs(
                credentials, config, existing_entities, all_created_entities
            )
            all_created_entities.update(created_entities)

            current_transactions = None
            if field == "investment":
                current_transactions = Transactions(investment=txs)
            elif field == "account":
                current_transactions = Transactions(account=txs)

            if current_transactions:
                transactions += current_transactions

        return transactions, set(all_created_entities.values())

    def _load_txs(
        self,
        credentials: GoogleCredentials,
        config: VirtualTransactionSheetConfig,
        existing_entities: dict[str, Entity],
        already_created_entities: dict[str, Entity],
    ) -> tuple[list[BaseTx], dict[str, Entity]]:
        txs = []
        created_entities = {}

        def process_entry_fn(row, tx_dict):
            tx_id = uuid4()
            tx_dict["id"] = tx_id
            tx_dict["is_real"] = False

            prod_type = tx_dict.get("product_type")
            if prod_type not in self.TX_PROD_TYPE_ATTR_MAP:
                self._log.warning(
                    f"Skipping row {row}: Invalid product type {prod_type}"
                )
                return

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

        self._parse_sheet_table(credentials, config, process_entry_fn)

        return txs, created_entities

    def _parse_sheet_table(
        self, credentials: GoogleCredentials, config: BaseSheetConfig, entry_fn
    ):
        sheet_range, sheet_id = config.range, config.spreadsheetId
        cells = self._read_sheet_table(credentials, sheet_id, sheet_range)
        if not cells:
            return {}

        header_row_index, start_column_index = next(
            (
                (index, next((i for i, x in enumerate(row) if x), None))
                for index, row in enumerate(cells)
                if row
            ),
            (None, None),
        )
        if header_row_index is None or start_column_index is None:
            return {}

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
                self._log.warning(f"Skipping row {row}: {e}")
                continue
            except ValidationError as e:
                self._log.warning(f"Skipping row {row}: {e}")
                continue

    def _read_sheet_table(
        self, credentials: GoogleCredentials, sheet_id, cell_range
    ) -> list[list]:
        sheets_service = self._sheets_service.service(credentials)
        result = (
            sheets_service.values()
            .get(spreadsheetId=sheet_id, range=cell_range)
            .execute()
        )
        return result.get("values", [])
