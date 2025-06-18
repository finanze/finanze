import inspect
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from application.ports.virtual_fetch import VirtualFetcher
from domain.entity import Entity, EntityType
from domain.exception.exceptions import MissingFieldsError
from domain.global_position import (
    Deposit,
    Deposits,
    FactoringDetail,
    FactoringInvestments,
    FundDetail,
    FundInvestments,
    GlobalPosition,
    Investments,
    RealStateCFDetail,
    RealStateCFInvestments,
    StockDetail,
    StockInvestments,
)
from domain.settings import (
    BaseSheetConfig,
    GoogleCredentials,
    VirtualInvestmentSheetConfig,
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


def parse_number(value: str) -> float:
    return float(value.strip().replace(".", "").replace(",", "."))


def total(products):
    return round(sum([product.amount for product in products]), 2)


def expected_interests(products):
    return round(sum([product.expected_interests for product in products]), 2)


def weighted_interest_rate(products):
    return round(
        sum([product.interest_rate * product.amount for product in products])
        / total(products),
        6,
    )


def initial_investment(products):
    return round(sum([product.initial_investment for product in products]), 2)


def market_value(products):
    return round(sum([product.market_value for product in products]), 2)


AGGR_FIELD_OPERATION = {
    "total": total,
    "invested": total,
    "expected_interests": expected_interests,
    "weighted_interest_rate": weighted_interest_rate,
    "investment": initial_investment,
    "market_value": market_value,
}


def _parse_cell(value: str, config: BaseSheetConfig) -> any:
    try:
        return parse_number(value)
    except ValueError:
        try:
            return datetime.strptime(value, config.datetimeFormat)
        except ValueError:
            try:
                return datetime.strptime(value, config.dateFormat).date()
            except ValueError:
                if not len(value):
                    return None
                return value


class SheetsImporter(VirtualFetcher):
    INV_TYPE_ATTR_MAP = {
        "deposits": (Deposits, Deposit),
        "funds": (FundInvestments, FundDetail),
        "stocks": (StockInvestments, StockDetail),
        "factoring": (FactoringInvestments, FactoringDetail),
        "real_state_cf": (RealStateCFInvestments, RealStateCFDetail),
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
        investment_configs: list[VirtualInvestmentSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> tuple[list[GlobalPosition], set[Entity]]:
        global_positions_dicts = {}
        for config in investment_configs:
            field = config.data
            parent_type, detail_type = self.INV_TYPE_ATTR_MAP.get(field, (None, None))
            if not parent_type:
                raise ValueError(f"Invalid field {field}")

            per_entity = self._load_investment_products(
                detail_type, parent_type, credentials, config
            )
            for entity in per_entity:
                if entity not in global_positions_dicts:
                    global_positions_dicts[entity] = {"investments": {}}

                global_positions_dicts[entity]["investments"][field] = per_entity[
                    entity
                ]

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

            investments = Investments(**data["investments"])
            global_positions.append(
                GlobalPosition(
                    id=uuid4(), entity=entity, investments=investments, is_real=False
                )
            )

        return global_positions, set(created_entities.values())

    def _load_investment_products(
        self,
        cls,
        parent_cls,
        credentials: GoogleCredentials,
        config: VirtualInvestmentSheetConfig,
    ) -> dict[str, any]:
        details_per_entity = {}

        def process_entry_fn(row, product_dict):
            p_id = uuid4()
            product_dict["id"] = p_id
            entity = product_dict["entity"]
            entity_products = details_per_entity.get(entity, [])
            entity_products.append(cls.from_dict(product_dict))

            details_per_entity[entity] = entity_products

        self._parse_sheet_table(credentials, config, process_entry_fn)

        if not details_per_entity:
            return {}

        per_entity = {}
        parent_params = inspect.signature(parent_cls).parameters
        for entity, entity_products in details_per_entity.items():
            parent_obj_dict = {}
            for param in parent_params:
                if param in AGGR_FIELD_OPERATION:
                    parent_obj_dict[param] = AGGR_FIELD_OPERATION[param](
                        entity_products
                    )

            parent_obj_dict["details"] = entity_products
            parent_obj_dict["currency"] = entity_products[0].currency
            per_entity[entity] = parent_cls(**parent_obj_dict)

        return per_entity

    async def transactions(
        self,
        credentials: GoogleCredentials,
        txs_configs: list[VirtualTransactionSheetConfig],
        registered_txs: set[str],
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
            txs = [tx for tx in txs if tx.ref not in registered_txs]

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
