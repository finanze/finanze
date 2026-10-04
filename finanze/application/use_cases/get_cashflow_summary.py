from datetime import date
from typing import Optional
from uuid import UUID

from application.ports.entity_port import EntityPort
from application.ports.exchange_rate_storage import ExchangeRateStorage
from application.ports.label_port import LabelPort
from application.ports.transaction_port import TransactionPort
from domain.cashflow import (
    CASHFLOW_TX_TYPES,
    CashflowQuery,
    CashflowSummary,
    aggregate_cashflow,
    previous_period,
    rate_converter,
)
from domain.labeling import LabelCategory
from domain.transactions import AccountTx, AccountTxSelection
from domain.use_cases.get_cashflow_summary import GetCashflowSummary


class GetCashflowSummaryImpl(GetCashflowSummary):
    def __init__(
        self,
        transaction_port: TransactionPort,
        label_port: LabelPort,
        entity_port: EntityPort,
        exchange_rate_storage: ExchangeRateStorage,
    ):
        self._transaction_port = transaction_port
        self._label_port = label_port
        self._entity_port = entity_port
        self._exchange_rate_storage = exchange_rate_storage

    async def execute(self, query: CashflowQuery) -> CashflowSummary:
        disabled = {e.id for e in await self._entity_port.get_disabled_entities()}
        excluded_labels = {
            label.id
            for label in await self._label_port.get_all()
            if label.category == LabelCategory.EXCLUDED
        }
        convert = rate_converter(
            await self._exchange_rate_storage.get(), query.currency
        )

        previous_from, previous_to = previous_period(query.from_date, query.to_date)
        txs = await self._get_txs(
            query.entities, query.from_date, query.to_date, disabled
        )
        previous_txs = await self._get_txs(
            query.entities, previous_from, previous_to, disabled
        )
        return aggregate_cashflow(txs, previous_txs, excluded_labels, convert, query)

    async def _get_txs(
        self,
        entities: Optional[list[UUID]],
        from_date: date,
        to_date: date,
        disabled: set[UUID],
    ) -> list[AccountTx]:
        txs = await self._transaction_port.get_account_txs(
            AccountTxSelection(
                from_date=from_date,
                to_date=to_date,
                entities=entities,
                types=CASHFLOW_TX_TYPES,
            )
        )
        return [tx for tx in txs if tx.entity.id not in disabled]
