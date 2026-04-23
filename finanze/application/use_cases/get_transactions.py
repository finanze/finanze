from application.ports.entity_port import EntityPort
from application.ports.transaction_port import TransactionPort
from domain.transactions import TransactionQueryRequest, TransactionsResult
from domain.use_cases.get_transactions import GetTransactions


class GetTransactionsImpl(GetTransactions):
    def __init__(self, transaction_port: TransactionPort, entity_port: EntityPort):
        self._transaction_port = transaction_port
        self._entity_port = entity_port

    async def execute(self, query: TransactionQueryRequest) -> TransactionsResult:
        excluded_entities = [
            e.id for e in await self._entity_port.get_disabled_entities()
        ]

        query.excluded_entities = excluded_entities
        txs = await self._transaction_port.get_by_filters(query)

        return TransactionsResult(transactions=txs)
