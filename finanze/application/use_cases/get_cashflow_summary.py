from datetime import date
from typing import Optional
from uuid import UUID

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.entity_port import EntityPort
from application.ports.exchange_rate_storage import ExchangeRateStorage
from application.ports.label_port import LabelPort
from application.ports.periodic_flow_port import PeriodicFlowPort
from application.ports.transaction_port import TransactionPort
from domain.auto_contributions import ContributionQueryRequest
from domain.budget import compare_budget
from domain.cashflow import (
    CASHFLOW_TX_TYPES,
    CashflowQuery,
    CashflowSummary,
    aggregate_cashflow,
    period_start,
    previous_period,
    rate_converter,
)
from domain.labeling import LabelCategory, LabelSubcategory
from domain.transactions import AccountTx, AccountTxSelection
from domain.use_cases.get_cashflow_summary import GetCashflowSummary


class GetCashflowSummaryImpl(GetCashflowSummary):
    def __init__(
        self,
        transaction_port: TransactionPort,
        label_port: LabelPort,
        entity_port: EntityPort,
        exchange_rate_storage: ExchangeRateStorage,
        periodic_flow_port: PeriodicFlowPort,
        auto_contributions_port: AutoContributionsPort,
    ):
        self._transaction_port = transaction_port
        self._label_port = label_port
        self._entity_port = entity_port
        self._exchange_rate_storage = exchange_rate_storage
        self._periodic_flow_port = periodic_flow_port
        self._auto_contributions_port = auto_contributions_port

    async def execute(self, query: CashflowQuery) -> CashflowSummary:
        disabled = {e.id for e in await self._entity_port.get_disabled_entities()}
        labels = await self._label_port.get_all()
        excluded_labels = {
            label.id for label in labels if label.category == LabelCategory.EXCLUDED
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
        summary = aggregate_cashflow(txs, previous_txs, excluded_labels, convert, query)
        if not query.entities:
            contributions = (
                await self._auto_contributions_port.get_all_grouped_by_entity(
                    ContributionQueryRequest(excluded_entities=list(disabled))
                )
            )
            investment_txs = await self._transaction_port.get_investment_txs_in_range(
                None, query.from_date, query.to_date
            )
            summary.budget = compare_budget(
                await self._periodic_flow_port.get_all(),
                query.from_date,
                query.to_date,
                summary.totals.income,
                summary.totals.expenses,
                {row.label_id: (row.income, row.expenses) for row in summary.by_label},
                excluded_labels,
                convert,
                actual_saved=summary.totals.net,
                contributions=[
                    contribution
                    for entity, group in contributions.items()
                    if entity.id not in disabled
                    for contribution in group.periodic
                ],
                investment_txs=[
                    tx for tx in investment_txs if tx.entity.id not in disabled
                ],
                account_txs=txs,
                savings_label_ids={
                    label.id
                    for label in labels
                    if label.category == LabelCategory.EXCLUDED
                    and label.subcategory == LabelSubcategory.SAVINGS
                },
                wants_label_ids={
                    label.id
                    for label in labels
                    if label.category == LabelCategory.EXPENSE
                    and label.subcategory == LabelSubcategory.WANTS
                },
                period_of=lambda day: period_start(day, query.granularity),
                income_by_period={
                    point.period: point.income for point in summary.series
                },
            )
        return summary

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
