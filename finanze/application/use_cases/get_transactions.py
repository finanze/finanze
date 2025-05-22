from application.ports.transaction_port import TransactionPort
from domain.transactions import TransactionQueryRequest, TransactionsResult
from domain.use_cases.get_transactions import GetTransactions


class GetTransactionsImpl(GetTransactions):

    def __init__(self, transaction_port: TransactionPort):
        self._transaction_port = transaction_port

    def execute(self, query: TransactionQueryRequest) -> TransactionsResult:
        txs = self._transaction_port.get_by_filters(query)
        return TransactionsResult(transactions=txs)
