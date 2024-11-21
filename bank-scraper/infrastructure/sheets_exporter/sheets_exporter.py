import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from application.ports.sheets_export_port import SheetsUpdatePort
from domain.bank_data import BankGlobalPosition
from infrastructure.sheets_exporter.sheets_funds_exporter import update_funds
from infrastructure.sheets_exporter.sheets_other_exporter import update_other
from infrastructure.sheets_exporter.sheets_stocks_exporter import update_stocks
from infrastructure.sheets_exporter.sheets_summary_exporter import update_summary

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

    def update(self, summary: dict[str, BankGlobalPosition]):
        update_summary(self.__sheet, summary, self.__spreadsheet_id)
        update_funds(self.__sheet, summary, self.__spreadsheet_id)
        update_stocks(self.__sheet, summary, self.__spreadsheet_id)
        update_other(self.__sheet, summary, self.__spreadsheet_id)
