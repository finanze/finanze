import os.path
from datetime import datetime

from application.ports.sheets_export_port import SheetsUpdatePort
from domain.auto_contributions import AutoContributions
from domain.global_position import GlobalPosition
from domain.transactions import Transactions
from infrastructure.sheets.exporter.sheets_object_exporter import update_sheet
from infrastructure.sheets.exporter.sheets_summary_exporter import update_summary
from infrastructure.sheets.sheets_base_loader import spreadsheets

FUNDS_SHEET = "Funds"
STOCKS_SHEET = "Stocks"
RSCF_SHEET = "Real State CF"
OTHER_SHEET = "Other"

CONTRIBUTIONS_SHEET = "Auto Contribuciones"

INVESTMENT_TXS_SHEET = "Investment TXs"
ACCOUNT_TXS_SHEET = "Account TXs"


class SheetsExporter(SheetsUpdatePort):

    def __init__(self):
        self.__sheet_id = os.environ["WRITE_SHEETS_IDS"]
        self.__sheet = spreadsheets()

    def update_global_position(self, global_position: dict[str, GlobalPosition]):
        update_summary(self.__sheet, global_position, self.__sheet_id)
        update_sheet(self.__sheet, global_position, self.__sheet_id, FUNDS_SHEET, "investments.funds.details")
        update_sheet(self.__sheet, global_position, self.__sheet_id, STOCKS_SHEET, "investments.stocks.details")
        update_sheet(self.__sheet, global_position, self.__sheet_id, RSCF_SHEET, "investments.realStateCF.details")
        update_sheet(self.__sheet, global_position, self.__sheet_id, OTHER_SHEET, ["investments.factoring.details"])

    def update_contributions(self, contributions: dict[str, AutoContributions], last_update: dict[str, datetime]):
        update_sheet(self.__sheet, contributions, self.__sheet_id, CONTRIBUTIONS_SHEET, ["periodic"], last_update)

    def update_transactions(self, transactions: Transactions, last_update: dict[str, datetime]):
        update_sheet(self.__sheet, transactions, self.__sheet_id, INVESTMENT_TXS_SHEET, ["investment"], last_update)
        update_sheet(self.__sheet, transactions, self.__sheet_id, ACCOUNT_TXS_SHEET, ["account"], last_update)
