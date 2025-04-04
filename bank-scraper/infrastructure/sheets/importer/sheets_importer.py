import inspect
import logging
from datetime import datetime
from typing import Optional

from pydantic import ValidationError

from application.ports.virtual_scraper import VirtualScraper
from domain.exception.exceptions import MissingFieldsError
from domain.global_position import GlobalPosition, SourceType, Deposits, Deposit, FundInvestments, \
    FactoringInvestments, RealStateCFInvestments, StockInvestments, StockDetail, FactoringDetail, RealStateCFDetail, \
    FundDetail, Investments
from domain.transactions import Transactions, StockTx, FundTx, RealStateCFTx, \
    FactoringTx
from infrastructure.sheets.sheets_base_loader import spreadsheets


def parse_number(value: str) -> float:
    return float(value.strip().replace(".", "").replace(",", "."))


def total(products):
    return round(sum([product.amount for product in products]), 2)


def total_interests(products):
    return round(sum([product.totalInterests for product in products]), 2)


def weighted_interest_rate(products):
    return round(sum([product.interestRate * product.amount for product in products]) / total(products), 6)


def initial_investment(products):
    return round(sum([product.initialInvestment for product in products]), 2)


def market_value(products):
    return round(sum([product.marketValue for product in products]), 2)


AGGR_FIELD_OPERATION = {
    "total": total,
    "invested": total,
    "totalInterests": total_interests,
    "weightedInterestRate": weighted_interest_rate,
    "initialInvestment": initial_investment,
    "marketValue": market_value
}


class SheetsImporter(VirtualScraper):
    INV_TYPE_ATTR_MAP = {
        "deposits": (Deposits, Deposit),
        "funds": (FundInvestments, FundDetail),
        "stocks": (StockInvestments, StockDetail),
        "factoring": (FactoringInvestments, FactoringDetail),
        "realStateCF": (RealStateCFInvestments, RealStateCFDetail),
    }

    TX_PROD_TYPE_ATTR_MAP = {
        "STOCK_ETF": StockTx,
        "FUND": FundTx,
        "REAL_STATE_CF": RealStateCFTx,
        "FACTORING": FactoringTx,
    }

    def __init__(self):
        self._sheet = spreadsheets()
        self._log = logging.getLogger(__name__)

    async def global_positions(self, investment_configs) -> dict[str, GlobalPosition]:
        global_positions_dicts = {}
        for config in investment_configs:
            field = config["data"]
            parent_type, detail_type = self.INV_TYPE_ATTR_MAP.get(field, (None, None))
            if not parent_type:
                raise ValueError(f"Invalid field {field}")

            per_entity = self._load_investment_products(detail_type, parent_type, config)
            for entity in per_entity:
                if entity not in global_positions_dicts:
                    global_positions_dicts[entity] = {"investments": {}}

                global_positions_dicts[entity]["investments"][field] = per_entity[entity]

        global_positions = {}
        for entity, data in global_positions_dicts.items():
            investments = Investments(**data["investments"])
            global_positions[entity] = GlobalPosition(investments=investments)

        return global_positions

    def _load_investment_products(self, cls, parent_cls, config) -> dict[str, any]:
        details_per_entity = {}

        def process_entry_fn(row, product_dict):
            entity = product_dict["entity"]
            entity_products = details_per_entity.get(entity, [])
            entity_products.append(cls.from_dict(product_dict))

            details_per_entity[entity] = entity_products

        self._parse_sheet_table(config, process_entry_fn)

        if not details_per_entity:
            return {}

        per_entity = {}
        parent_params = inspect.signature(parent_cls).parameters
        for entity, entity_products in details_per_entity.items():
            parent_obj_dict = {}
            for param in parent_params:
                if param in AGGR_FIELD_OPERATION:
                    parent_obj_dict[param] = AGGR_FIELD_OPERATION[param](entity_products)

            parent_obj_dict["details"] = entity_products
            per_entity[entity] = parent_cls(**parent_obj_dict)

        return per_entity

    async def transactions(self, txs_configs, registered_txs: set[str]) -> Optional[Transactions]:
        transactions = Transactions(investment=[], account=[])

        for config in txs_configs:
            field = config["data"]

            txs = self._load_inv_txs(config)
            txs = [tx for tx in txs if tx.ref not in registered_txs]

            current_transactions = None
            if field == "investment":
                current_transactions = Transactions(investment=txs)
            elif field == "account":
                current_transactions = Transactions(account=txs)

            if current_transactions:
                transactions += current_transactions

        return transactions

    def _load_inv_txs(self, config) -> list:
        txs = []

        def process_entry_fn(row, tx_dict):
            tx_dict["sourceType"] = SourceType.VIRTUAL

            prod_type = tx_dict.get("productType")
            if prod_type not in self.TX_PROD_TYPE_ATTR_MAP:
                self._log.warn(f"Skipping row {row}: Invalid product type {prod_type}")
                return

            cls = self.TX_PROD_TYPE_ATTR_MAP[prod_type]
            txs.append(cls.from_dict(tx_dict))

        self._parse_sheet_table(config, process_entry_fn)

        return txs

    def _parse_sheet_table(self, config, entry_fn):
        sheet_range, sheet_id = config["range"], config["spreadsheetId"]
        cells = self._read_sheet_table(sheet_id, sheet_range)
        if not cells:
            return {}

        header_row_index, start_column_index = next(((index, next((i for i, x in enumerate(row) if x), None))
                                                     for index, row in enumerate(cells) if row),
                                                    (None, None))
        if header_row_index is None or start_column_index is None:
            return {}

        columns = cells[header_row_index][start_column_index:]

        for row in cells[header_row_index + 1:]:
            entry_dict = {}
            for j, column in enumerate(columns, start_column_index):
                if not column or j >= len(row):
                    continue
                parsed = self._parse_cell(row[j], config)
                if parsed is not None:
                    entry_dict[column] = parsed

            try:
                entry_fn(row, entry_dict)
            except MissingFieldsError as e:
                self._log.warn(f"Skipping row {row}: {e}")
                continue
            except ValidationError as e:
                self._log.warn(f"Skipping row {row}: {e}")
                continue

    def _parse_cell(self, value: str, config: dict) -> any:
        try:
            return parse_number(value)
        except ValueError:
            try:
                return datetime.strptime(value, config["datetimeFormat"])
            except ValueError:
                try:
                    return datetime.strptime(value, config["dateFormat"]).date()
                except ValueError:
                    if not len(value):
                        return None
                    return value

    def _read_sheet_table(self, sheet_id, cell_range) -> list[list]:
        result = self._sheet.values().get(spreadsheetId=sheet_id, range=cell_range).execute()
        return result.get('values', [])
