import os.path
from datetime import datetime

from application.ports.sheets_export_port import SheetsUpdatePort
from domain.auto_contributions import AutoContributions
from domain.global_position import GlobalPosition
from domain.transactions import Transactions
from infrastructure.sheets.exporter.sheets_contribs_exporter import update_contributions
from infrastructure.sheets.exporter.sheets_funds_exporter import update_funds
from infrastructure.sheets.exporter.sheets_other_exporter import update_other
from infrastructure.sheets.exporter.sheets_rscf_exporter import update_rscf
from infrastructure.sheets.exporter.sheets_stocks_exporter import update_stocks
from infrastructure.sheets.exporter.sheets_summary_exporter import update_summary
from infrastructure.sheets.exporter.sheets_txs_exporter import update_transactions
from infrastructure.sheets.sheets_base_loader import spreadsheets


class SheetsExporter(SheetsUpdatePort):

    def __init__(self):
        self.__sheet_id = os.environ["WRITE_SHEETS_IDS"]
        self.__sheet = spreadsheets()

    def update_global_position(self, global_position: dict[str, GlobalPosition]):
        update_summary(self.__sheet, global_position, self.__sheet_id)
        update_funds(self.__sheet, global_position, self.__sheet_id)
        update_stocks(self.__sheet, global_position, self.__sheet_id)
        update_other(self.__sheet, global_position, self.__sheet_id)
        update_rscf(self.__sheet, global_position, self.__sheet_id)

    def update_contributions(self, contributions: dict[str, AutoContributions], last_update: dict[str, datetime]):
        update_contributions(self.__sheet, contributions, self.__sheet_id, last_update)

    def update_transactions(self, transactions: Transactions, last_update: dict[str, datetime]):
        update_transactions(self.__sheet, transactions, self.__sheet_id, last_update)
