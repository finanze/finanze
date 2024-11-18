from application.ports.bank_data_port import BankDataPort
from application.ports.sheets_export_port import SheetsUpdatePort
from domain.use_cases.update_sheets import UpdateSheets


class UpdateSheetsImpl(UpdateSheets):
    def __init__(self, bank_data_port: BankDataPort, sheets_update_port: SheetsUpdatePort):
        self.bank_data_port = bank_data_port
        self.sheets_update_port = sheets_update_port

    def execute(self):
        global_summary = self.bank_data_port.get_all_data()
        self.sheets_update_port.update(global_summary)
