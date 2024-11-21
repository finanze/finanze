from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.bank_data_port import BankDataPort
from application.ports.sheets_export_port import SheetsUpdatePort
from domain.use_cases.update_sheets import UpdateSheets


class UpdateSheetsImpl(UpdateSheets):
    def __init__(self,
                 bank_data_port: BankDataPort,
                 auto_contr_port: AutoContributionsPort,
                 sheets_update_port: SheetsUpdatePort):
        self.bank_data_port = bank_data_port
        self.auto_contr_port = auto_contr_port
        self.sheets_update_port = sheets_update_port

    def execute(self):
        global_position = self.bank_data_port.get_all_data()
        self.sheets_update_port.update_global_position(global_position)

        auto_contributions = self.auto_contr_port.get_all()
        self.sheets_update_port.update_contributions(auto_contributions)
