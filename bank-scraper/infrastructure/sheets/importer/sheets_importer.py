import os
from datetime import datetime
from typing import Optional

from application.ports.virtual_scraper import VirtualScraper
from domain.global_position import GlobalPosition, Deposits, Deposit, SourceType, Investments
from domain.transactions import Transactions, TxType, TxProductType, StockTx, FundTx, RealStateCFTx, \
    FactoringTx
from infrastructure.sheets.sheets_base_loader import spreadsheets


def parse_number(value: str) -> float:
    return float(value.strip()[:-1].strip().replace(".", "").replace(",", "."))


class SheetsImporter(VirtualScraper):
    DEPOSITS_RANGE = "Deposits!A2:Z"
    INVESTMENT_TXS_RANGE = "Investment TXs!A2:Z"

    DATE_FORMAT = "%d/%m/%Y"
    DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"

    def __init__(self):
        self.__sheet_id = os.environ["READ_SHEETS_IDS"]
        self.__sheet = spreadsheets()

    async def global_positions(self) -> dict[str, GlobalPosition]:
        available_entities = set()
        deposits_per_entity = self.load_deposits()
        if deposits_per_entity:
            available_entities.update(deposits_per_entity.keys())

        global_positions = {}
        for entity in available_entities:
            deposits = deposits_per_entity.get(entity, None)

            global_positions[entity] = GlobalPosition(
                investments=Investments(deposits=deposits)
            )

        return global_positions

    def load_deposits(self) -> dict[str, Deposits]:
        result = self.__read_sheet_table(self.DEPOSITS_RANGE)
        if not result:
            return {}

        deposit_details_per_entity = {}
        for row in result:
            name = row[0]
            amount = round(parse_number(row[1]), 2)
            interest_rate = round(parse_number(row[4]) / 100, 6)
            interest = round(parse_number(row[5]), 2)
            start = datetime.strptime(row[6], self.DATETIME_FORMAT).date()
            maturity = datetime.strptime(row[7], self.DATE_FORMAT)
            entity = row[8]

            entity_deposits = deposit_details_per_entity.get(entity, [])
            entity_deposits.append(Deposit(
                name=name,
                amount=amount,
                interestRate=interest_rate,
                totalInterests=interest,
                creation=start,
                maturity=maturity
            ))
            deposit_details_per_entity[entity] = entity_deposits

        deposits_per_entity = {}
        for entity, entity_deposits in deposit_details_per_entity.items():
            total = sum([deposit.amount for deposit in entity_deposits])
            total_interests = sum([deposit.totalInterests for deposit in entity_deposits])
            weighted_interest_rate = sum([deposit.interestRate * deposit.amount for deposit in entity_deposits]) / total

            deposits_per_entity[entity] = Deposits(
                total=round(total, 2),
                totalInterests=round(total_interests, 2),
                weightedInterestRate=round(weighted_interest_rate, 6),
                details=entity_deposits
            )

        return deposits_per_entity

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

    def __read_sheet_table(self, cell_range) -> list[list]:
        result = self.__sheet.values().get(spreadsheetId=self.__sheet_id, range=cell_range).execute()
        return result.get('values', [])
