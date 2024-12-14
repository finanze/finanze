from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.position_port import PositionPort
from application.ports.sheets_export_port import SheetsUpdatePort
from application.ports.transaction_port import TransactionPort
from domain.use_cases.update_sheets import UpdateSheets


class UpdateSheetsImpl(UpdateSheets):
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
        self.sheets_update_port.update_global_position(global_position)

        auto_contributions = self.auto_contr_port.get_all_grouped_by_entity()
        auto_contributions_last_update = self.auto_contr_port.get_last_update_grouped_by_entity()
        self.sheets_update_port.update_contributions(auto_contributions, auto_contributions_last_update)

        transactions = self.transaction_port.get_all()
        transactions_last_update = self.transaction_port.get_last_created_grouped_by_entity()
        self.sheets_update_port.update_transactions(transactions, transactions_last_update)
