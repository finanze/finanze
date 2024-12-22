import inspect
import os
from datetime import datetime
from typing import Optional

from application.ports.virtual_scraper import VirtualScraper
from domain.exception.exceptions import MissingFieldsError
from domain.global_position import GlobalPosition, SourceType, Deposits, Deposit, FundInvestments, \
    FactoringInvestments, RealStateCFInvestments, StockInvestments, StockDetail, FactoringDetail, RealStateCFDetail, \
    FundDetail, Investments
from domain.transactions import Transactions, TxType, TxProductType, StockTx, FundTx, RealStateCFTx, \
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
    INVESTMENT_TXS_RANGE = "Investment TXs!A2:Z"

    DATE_FORMAT = "%d/%m/%Y"
    DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"

    IMPORT_CONFIG = {
        "investments": {
            "Deposits": "deposits",
        },
        "transactions": {
            "Account TXs": "account"
        }
    }

    INV_TYPE_ATTR_MAP = {
        "deposits": (Deposits, Deposit),
        "funds": (FundInvestments, FundDetail),
        "stocks": (StockInvestments, StockDetail),
        "factoring": (FactoringInvestments, FactoringDetail),
        "realStateCF": (RealStateCFInvestments, RealStateCFDetail),
    }

    def __init__(self):
        self.__sheet_id = os.environ["READ_SHEETS_IDS"]
        self.__sheet = spreadsheets()

    async def global_positions(self) -> dict[str, GlobalPosition]:
        global_positions_dicts = {}
        for sheet_range, field in self.IMPORT_CONFIG["investments"].items():
            parent_type, detail_type = self.INV_TYPE_ATTR_MAP.get(field, (None, None))
            if not parent_type:
                raise ValueError(f"Invalid field {field}")

            per_entity = self.load_investment_products(detail_type, parent_type, sheet_range)
            for entity in per_entity:
                if entity not in global_positions_dicts:
                    global_positions_dicts[entity] = {"investments": {}}

                global_positions_dicts[entity]["investments"][field] = per_entity[entity]

        global_positions = {}
        for entity, data in global_positions_dicts.items():
            investments = Investments(**data["investments"])
            global_positions[entity] = GlobalPosition(investments=investments)

        return global_positions

    def load_investment_products(self, cls, parent_cls, sheet_range) -> dict[str, any]:
        cells = self.__read_sheet_table(sheet_range)
        if not cells:
            return {}

        header_row_index, start_column_index = next(((index, next((i for i, x in enumerate(row) if x), None))
                                                     for index, row in enumerate(cells) if row),
                                                    (None, None))
        if header_row_index is None or start_column_index is None:
            return {}

        columns = cells[header_row_index][start_column_index:]

        details_per_entity = {}
        for row in cells[header_row_index + 1:]:
            product_dict = {}
            for j, column in enumerate(columns, start_column_index):
                if not column:
                    continue
                parsed = self.parse_cell(row[j])
                if parsed is not None:
                    product_dict[column] = parsed

            entity = product_dict["entity"]
            entity_products = details_per_entity.get(entity, [])
            try:
                entity_products.append(cls.from_dict(product_dict))
            except MissingFieldsError as e:
                print(f"Skipping row {row}: {e}")
                continue

            details_per_entity[entity] = entity_products

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

    async def transactions(self, registered_txs: set[str]) -> Optional[Transactions]:
        result = self.__read_sheet_table(self.INVESTMENT_TXS_RANGE)
        if not result:
            return None

        inv_txs = []
        for row in result:
            tx_id = row[0]
            if not tx_id or tx_id in registered_txs:
                continue

            raw_tx_type = row[5]
            tx_type = TxType(raw_tx_type)
            raw_product_type = row[9]
            product_type = TxProductType(raw_product_type)
            base_tx = {
                "id": tx_id,
                "name": row[1],
                "amount": parse_number(row[2]),
                "currency": row[3],
                "currencySymbol": row[4],
                "type": tx_type,
                "date": datetime.strptime(row[6], self.DATETIME_FORMAT if len(row[6]) > 10 else self.DATE_FORMAT),
                "entity": row[7],
                "productType": product_type,
                "sourceType": SourceType.VIRTUAL
            }

            columns = len(row)
            tx = None
            if product_type in [TxProductType.STOCK_ETF, TxProductType.FUND]:
                base_tx["netAmount"] = parse_number(row[10])
                base_tx["isin"] = row[11]
                base_tx["shares"] = float(row[13])
                base_tx["price"] = parse_number(row[14])
                base_tx["market"] = row[15]
                base_tx["fees"] = parse_number(row[16])
                base_tx["orderDate"] = datetime.strptime(row[17], self.DATETIME_FORMAT) if columns > 17 and row[
                    17] else None
                base_tx["retentions"] = parse_number(row[18]) if columns > 18 and row[18] else None

                if product_type == TxProductType.STOCK_ETF:
                    base_tx["ticker"] = row[12]
                    base_tx["linkedTx"] = row[19] if columns > 19 and row[19] else None
                    tx = StockTx(**base_tx)
                else:
                    tx = FundTx(**base_tx)

            elif product_type in [TxProductType.FACTORING, TxProductType.REAL_STATE_CF]:
                base_tx["fees"] = parse_number(row[16]) if columns > 16 and row[16] else None
                base_tx["retentions"] = parse_number(row[18]) if columns > 18 and row[18] else None
                base_tx["interests"] = parse_number(row[20]) if columns > 20 and row[20] else None

                if product_type == TxProductType.FACTORING:
                    tx = FactoringTx(**base_tx)
                else:
                    tx = RealStateCFTx(**base_tx)

            inv_txs.append(tx)

        return Transactions(
            investment=inv_txs
        )

    def parse_cell(self, value: str):
        try:
            return parse_number(value)
        except ValueError:
            try:
                return datetime.strptime(value, self.DATETIME_FORMAT)
            except ValueError:
                try:
                    return datetime.strptime(value, self.DATE_FORMAT)
                except ValueError:
                    if not len(value):
                        return None
                    return value

    def __read_sheet_table(self, cell_range) -> list[list]:
        result = self.__sheet.values().get(spreadsheetId=self.__sheet_id, range=cell_range).execute()
        return result.get('values', [])
