from datetime import datetime

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.position_port import PositionPort
from application.ports.sheets_export_port import SheetsUpdatePort
from application.ports.transaction_port import TransactionPort
from domain.auto_contributions import AutoContributions
from domain.global_position import GlobalPosition
from domain.transactions import Transactions
from domain.use_cases.update_sheets import UpdateSheets

DETAILS_FIELD = "details"
ADDITIONAL_DATA_FIELD = "additionalData"


class UpdateSheetsImpl(UpdateSheets):
    SHEET_CONFIG = {
        "summary": "Summary",
        "investments": {
            "Funds": "funds",
            "Stocks": "stocks",
            "Real State CF": "realStateCF",
            "Other": ["factoring"]
        },
        "contributions": {
            "Auto Contribuciones": ["periodic"]
        },
        "transactions": {
            "Investment TXs": ["investment"],
            "Account TXs": ["account"]
        }
    }

    def __init__(self,
                 position_port: PositionPort,
                 auto_contr_port: AutoContributionsPort,
                 transaction_port: TransactionPort,
                 sheets_update_port: SheetsUpdatePort):
        self.position_port = position_port
        self.auto_contr_port = auto_contr_port
        self.transaction_port = transaction_port
        self.sheets_update_port = sheets_update_port

    def execute(self):
        global_position = self.position_port.get_last_grouped_by_entity()
        self.sheets_update_port.update_summary(global_position, self.SHEET_CONFIG["summary"])
        self.update_investment_sheets(global_position)

        auto_contributions = self.auto_contr_port.get_all_grouped_by_entity()
        auto_contributions_last_update = self.auto_contr_port.get_last_update_grouped_by_entity()
        self.update_contributions(auto_contributions, auto_contributions_last_update)

        transactions = self.transaction_port.get_all()
        transactions_last_update = self.transaction_port.get_last_created_grouped_by_entity()
        self.update_transactions(transactions, transactions_last_update)

    def update_investment_sheets(self, global_position: dict[str, GlobalPosition]):
        for sheet_name, fields in self.SHEET_CONFIG["investments"].items():
            fields = [fields] if isinstance(fields, str) else fields
            composed_fields = [f"investments.{field}.{DETAILS_FIELD}" for field in fields]

            self.sheets_update_port.update_sheet(global_position, sheet_name, composed_fields)

    def update_contributions(self, contributions: dict[str, AutoContributions], last_update: dict[str, datetime]):
        for sheet_name, fields in self.SHEET_CONFIG["contributions"].items():
            fields = [fields] if isinstance(fields, str) else fields
            self.sheets_update_port.update_sheet(contributions, sheet_name, fields, last_update)

    def update_transactions(self, transactions: Transactions, last_update: dict[str, datetime]):
        for sheet_name, fields in self.SHEET_CONFIG["transactions"].items():
            fields = [fields] if isinstance(fields, str) else fields
            self.sheets_update_port.update_sheet(transactions, sheet_name, fields, last_update)
