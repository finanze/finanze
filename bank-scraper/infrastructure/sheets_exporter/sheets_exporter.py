import os.path
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from application.ports.sheets_export_port import SheetsUpdatePort
from domain.auto_contributions import AutoContributions
from domain.bank_data import BankGlobalPosition
from domain.transactions import Transactions
from infrastructure.sheets_exporter.sheets_contribs_exporter import update_contributions
from infrastructure.sheets_exporter.sheets_funds_exporter import update_funds
from infrastructure.sheets_exporter.sheets_other_exporter import update_other
from infrastructure.sheets_exporter.sheets_stocks_exporter import update_stocks
from infrastructure.sheets_exporter.sheets_summary_exporter import update_summary
from infrastructure.sheets_exporter.sheets_txs_exporter import update_transactions

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsExporter(SheetsUpdatePort):

    def __init__(self):
        self.__spreadsheet_id = os.environ["GOOGLE_SPREADSHEET_ID"]
        creds = SheetsExporter.__load_creds()
        service = build("sheets", "v4", credentials=creds)
        self.__sheet = service.spreadsheets()

    @staticmethod
    def __load_creds():
        credentials_path = os.environ["GOOGLE_CREDENTIALS_PATH"]
        token_path = os.environ["GOOGLE_TOKEN_PATH"]

        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return creds

    def update_global_position(self, global_position: dict[str, BankGlobalPosition]):
        update_summary(self.__sheet, global_position, self.__spreadsheet_id)
        update_funds(self.__sheet, global_position, self.__spreadsheet_id)
        update_stocks(self.__sheet, global_position, self.__spreadsheet_id)
        update_other(self.__sheet, global_position, self.__spreadsheet_id)

    def update_contributions(self, contributions: dict[str, AutoContributions], last_update: dict[str, datetime]):
        update_contributions(self.__sheet, contributions, self.__spreadsheet_id, last_update)

    def update_transactions(self, transactions: Transactions, last_update: dict[str, datetime]):
        update_transactions(self.__sheet, transactions, self.__spreadsheet_id, last_update)
