import os
from datetime import datetime

from application.ports.virtual_scraper import VirtualScraper
from domain.global_position import GlobalPosition, Deposits, Deposit
from domain.transactions import Transactions
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
                deposits=deposits
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

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        return None

    def __read_sheet_table(self, cell_range) -> list[list]:
        result = self.__sheet.values().get(spreadsheetId=self.__sheet_id, range=cell_range).execute()
        return result.get('values', [])
