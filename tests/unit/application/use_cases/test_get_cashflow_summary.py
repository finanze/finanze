from datetime import date, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.entity_port import EntityPort
from application.ports.exchange_rate_storage import ExchangeRateStorage
from application.ports.label_port import LabelPort
from application.ports.periodic_flow_port import PeriodicFlowPort
from application.ports.transaction_port import TransactionPort
from application.use_cases.get_cashflow_summary import GetCashflowSummaryImpl
from domain.cashflow import CashflowGranularity, CashflowQuery
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.labeling import Label, LabelCategory, LabelSubcategory
from domain.transactions import AccountTx, LabelOrigin, TxLabel, TxType


@pytest.mark.asyncio
@pytest.mark.parametrize("filtered", [False, True])
async def test_global_budget_loads_expected_flows_once_only_without_entity_filter(
    filtered,
):
    txs = AsyncMock(spec=TransactionPort)
    txs.get_account_txs.return_value = []
    txs.get_investment_txs_in_range.return_value = []
    labels = AsyncMock(spec=LabelPort)
    wants_label = Label(
        id=uuid4(),
        name="Leisure",
        category=LabelCategory.EXPENSE,
        subcategory=LabelSubcategory.WANTS,
    )
    labels.get_all.return_value = [wants_label]
    entities = AsyncMock(spec=EntityPort)
    entities.get_disabled_entities.return_value = []
    rates = AsyncMock(spec=ExchangeRateStorage)
    rates.get.return_value = {}
    flows = AsyncMock(spec=PeriodicFlowPort)
    flows.get_all.return_value = [
        PeriodicFlow(
            id=uuid4(),
            name="Leisure",
            amount=Dezimal("120"),
            currency="EUR",
            flow_type=FlowType.EXPENSE,
            frequency=FlowFrequency.MONTHLY,
            category=None,
            enabled=True,
            since=date(2025, 1, 1),
            until=None,
            icon=None,
            label_id=wants_label.id,
        )
    ]
    contributions = AsyncMock(spec=AutoContributionsPort)
    contributions.get_all_grouped_by_entity.return_value = {}
    result = await GetCashflowSummaryImpl(
        txs, labels, entities, rates, flows, contributions
    ).execute(
        CashflowQuery(
            currency="EUR",
            from_date=date(2025, 3, 1),
            to_date=date(2025, 3, 11),
            entities=[uuid4()] if filtered else None,
        )
    )
    if filtered:
        flows.get_all.assert_not_awaited()
        contributions.get_all_grouped_by_entity.assert_not_awaited()
        txs.get_investment_txs_in_range.assert_not_awaited()
        assert result.budget is None
    else:
        flows.get_all.assert_awaited_once_with()
        contributions.get_all_grouped_by_entity.assert_awaited_once()
        assert (
            contributions.get_all_grouped_by_entity.call_args.args[0].excluded_entities
            == []
        )
        txs.get_investment_txs_in_range.assert_awaited_once_with(
            None, date(2025, 3, 1), date(2025, 3, 11)
        )
        assert result.budget.entry_count == 1
        assert result.budget.wants.expected == Dezimal("120")
        assert result.budget.needs.expected == 0
    labels.get_all.assert_awaited_once_with()
    rates.get.assert_awaited_once_with()
    assert txs.get_account_txs.await_count == 2


@pytest.mark.asyncio
async def test_budget_series_follows_requested_granularity():
    entity = Entity(
        id=uuid4(),
        name="Bank",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )
    wants_label = Label(
        id=uuid4(),
        name="Leisure",
        category=LabelCategory.EXPENSE,
        subcategory=LabelSubcategory.WANTS,
    )

    def account_tx(amount, tx_type, day, labels=()):
        return AccountTx(
            id=uuid4(),
            ref=str(uuid4()),
            name="Movement",
            amount=Dezimal(amount),
            currency="EUR",
            type=tx_type,
            date=datetime(2025, 3, day, 12, tzinfo=tzlocal()),
            entity=entity,
            source=DataSource.REAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal(0),
            retentions=Dezimal(0),
            labels=[
                TxLabel(label_id=label_id, origin=LabelOrigin.MANUAL)
                for label_id in labels
            ],
        )

    txs = AsyncMock(spec=TransactionPort)
    txs.get_account_txs.side_effect = [
        [
            account_tx("500", TxType.INFLOW, 1),
            account_tx("80", TxType.OUTFLOW, 2, [wants_label.id]),
        ],
        [],
    ]
    txs.get_investment_txs_in_range.return_value = []
    labels = AsyncMock(spec=LabelPort)
    labels.get_all.return_value = [wants_label]
    entities = AsyncMock(spec=EntityPort)
    entities.get_disabled_entities.return_value = []
    rates = AsyncMock(spec=ExchangeRateStorage)
    rates.get.return_value = {}
    flows = AsyncMock(spec=PeriodicFlowPort)
    flows.get_all.return_value = []
    contributions = AsyncMock(spec=AutoContributionsPort)
    contributions.get_all_grouped_by_entity.return_value = {}

    result = await GetCashflowSummaryImpl(
        txs, labels, entities, rates, flows, contributions
    ).execute(
        CashflowQuery(
            currency="EUR",
            from_date=date(2025, 3, 1),
            to_date=date(2025, 3, 11),
            granularity=CashflowGranularity.DAY,
        )
    )

    assert [
        (p.period, p.needs, p.wants, p.invested, p.remainder)
        for p in result.budget.series
    ] == [
        (date(2025, 3, 1), Dezimal(0), Dezimal(0), Dezimal(0), Dezimal(500)),
        (date(2025, 3, 2), Dezimal(0), Dezimal(80), Dezimal(0), Dezimal(-80)),
    ]
    assert result.series[1].expenses_by_label[0].label_id == wants_label.id
