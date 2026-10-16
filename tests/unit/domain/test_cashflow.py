from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from domain.auto_contributions import (
    ContributionFrequency,
    ContributionTargetType,
    PeriodicContribution,
)
from domain.budget import (
    CONTRIBUTION_MONTHLY_MULTIPLIERS,
    MONTHLY_MULTIPLIERS,
    compare_budget,
    target_months,
)
from domain.cashflow import (
    CashflowGranularity,
    CashflowQuery,
    IgnoredRecurringMovement,
    aggregate_cashflow,
    detect_recurring,
    period_start,
    previous_period,
    rate_converter,
)
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.transactions import (
    AccountTx,
    BaseInvestmentTx,
    LabelOrigin,
    TxLabel,
    TxType,
)

ENTITY = Entity(
    id=uuid4(),
    name="Bank",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.MANUAL,
    icon_url=None,
)
RATES = {"EUR": {"USD": Dezimal("1.25")}}


def _tx(amount, tx_type, day, name="Shop", currency="EUR", labels=None, **kwargs):
    return AccountTx(
        id=uuid4(),
        ref=str(uuid4()),
        name=name,
        amount=Dezimal(amount),
        currency=currency,
        type=tx_type,
        date=datetime(day.year, day.month, day.day, 12, tzinfo=tzlocal()),
        entity=ENTITY,
        source=DataSource.REAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        labels=[
            TxLabel(label_id=label_id, origin=LabelOrigin.RULE)
            for label_id in labels or []
        ],
        **kwargs,
    )


def test_previous_period_has_same_length():
    assert previous_period(date(2025, 3, 1), date(2025, 3, 31)) == (
        date(2025, 1, 29),
        date(2025, 2, 28),
    )


def test_rate_converter():
    convert = rate_converter(RATES, "EUR")
    assert convert(Dezimal(125), "USD") == Dezimal(100)
    assert convert(Dezimal(5), "EUR") == Dezimal(5)
    assert convert(Dezimal(5), "GBP") is None


def test_aggregate_excludes_linked_and_excluded_labels():
    groceries, transfer = uuid4(), uuid4()
    txs = [
        _tx("2000", TxType.INFLOW, date(2025, 3, 1), name="Payroll"),
        _tx(
            "125", TxType.OUTFLOW, date(2025, 3, 5), currency="USD", labels=[groceries]
        ),
        _tx("50", TxType.OUTFLOW, date(2025, 4, 2), labels=[groceries]),
        _tx("10", TxType.FEE, date(2025, 4, 3), name="Fee"),
        _tx("500", TxType.OUTFLOW, date(2025, 3, 6), labels=[transfer]),
        _tx("300", TxType.OUTFLOW, date(2025, 3, 7), linked_tx="buy-1"),
    ]
    previous = [_tx("1000", TxType.INFLOW, date(2025, 1, 1))]
    query = CashflowQuery(
        currency="EUR",
        from_date=date(2025, 3, 1),
        to_date=date(2025, 4, 30),
        granularity=CashflowGranularity.MONTH,
    )

    summary = aggregate_cashflow(
        txs, previous, {transfer}, rate_converter(RATES, "EUR"), query
    )

    assert summary.totals.income == Dezimal(2000)
    assert summary.totals.expenses == Dezimal(160)
    assert summary.totals.net == Dezimal(1840)
    assert summary.totals.count == 4
    assert summary.totals.savings_rate == Dezimal("0.92")
    assert summary.excluded_count == 2
    assert summary.previous.income == Dezimal(1000)
    assert [(p.period, p.income, p.expenses, p.count) for p in summary.series] == [
        (date(2025, 3, 1), Dezimal(2000), Dezimal(100), 2),
        (date(2025, 4, 1), Dezimal(0), Dezimal(60), 2),
    ]
    by_label = {b.label_id: b for b in summary.by_label}
    assert by_label[groceries].expenses == Dezimal(150)
    assert by_label[None].income == Dezimal(2000)
    assert summary.top_counterparties[0].name == "Payroll"


def test_aggregate_counterparty_labels_ordered_by_frequency():
    rent, home, misc = uuid4(), uuid4(), uuid4()
    txs = [
        _tx("900", TxType.OUTFLOW, date(2025, 3, 1), name="Landlord", labels=[misc]),
        _tx(
            "900",
            TxType.OUTFLOW,
            date(2025, 4, 1),
            name="Landlord",
            labels=[rent, home, rent],
        ),
        _tx("900", TxType.OUTFLOW, date(2025, 5, 1), name="Landlord", labels=[rent]),
        _tx("900", TxType.OUTFLOW, date(2025, 6, 1), name="Landlord"),
        _tx("20", TxType.OUTFLOW, date(2025, 3, 2), name="Kiosk"),
    ]
    query = CashflowQuery(
        currency="EUR", from_date=date(2025, 3, 1), to_date=date(2025, 6, 30)
    )

    summary = aggregate_cashflow(txs, [], set(), rate_converter(RATES, "EUR"), query)

    counterparties = {c.name: c for c in summary.top_counterparties}
    assert counterparties["Landlord"].label_ids == [rent, misc, home]
    assert counterparties["Kiosk"].label_ids == []


def test_aggregate_uses_net_amount_for_interest():
    gross_only = _tx("50", TxType.INTEREST, date(2025, 3, 2), name="Interest 2")
    gross_only.retentions = Dezimal("9.5")
    txs = [
        _tx(
            "100",
            TxType.INTEREST,
            date(2025, 3, 1),
            name="Interest",
            net_amount=Dezimal("81"),
        ),
        gross_only,
    ]
    query = CashflowQuery(
        currency="EUR", from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)
    )

    summary = aggregate_cashflow(txs, [], set(), rate_converter(RATES, "EUR"), query)

    assert summary.totals.income == Dezimal("121.5")
    assert summary.series[0].income == Dezimal("121.5")


def test_aggregate_splits_period_expenses_by_label_once_per_movement():
    food, home = uuid4(), uuid4()
    txs = [
        _tx("1000", TxType.INFLOW, date(2025, 3, 1), labels=[food]),
        _tx("100", TxType.OUTFLOW, date(2025, 3, 2), labels=[food, home, food]),
        _tx("125", TxType.OUTFLOW, date(2025, 3, 3), currency="USD", labels=[food]),
        _tx("30", TxType.FEE, date(2025, 3, 4)),
        _tx("20", TxType.OUTFLOW, date(2025, 4, 1), labels=[home]),
    ]
    query = CashflowQuery(
        currency="EUR", from_date=date(2025, 3, 1), to_date=date(2025, 4, 30)
    )

    summary = aggregate_cashflow(txs, [], set(), rate_converter(RATES, "EUR"), query)

    march, april = summary.series
    assert [(row.label_id, row.amount) for row in march.expenses_by_label] == [
        (food, Dezimal(150)),
        (home, Dezimal(50)),
        (None, Dezimal(30)),
    ]
    assert sum(row.amount for row in march.expenses_by_label) == march.expenses
    assert [(row.label_id, row.amount) for row in april.expenses_by_label] == [
        (home, Dezimal(20))
    ]


def _monthly(name, amounts, tx_type, last, **kwargs):
    return [
        _tx(
            amount,
            tx_type,
            last - timedelta(days=30 * (len(amounts) - 1 - i)),
            name=name,
            **kwargs,
        )
        for i, amount in enumerate(amounts)
    ]


def test_detect_fixed_and_variable_monthly_movements():
    today = date(2025, 6, 10)
    netflix = _monthly(
        "NETFLIX.COM 1234", ["12.99"] * 5, TxType.OUTFLOW, date(2025, 6, 1)
    )
    power = _monthly(
        "Iberdrola", ["60", "75", "52", "80"], TxType.OUTFLOW, date(2025, 6, 3)
    )
    random = [
        _tx("30", TxType.OUTFLOW, date(2025, 1, 3), name="Bar"),
        _tx("12", TxType.OUTFLOW, date(2025, 5, 20), name="Bar"),
    ]
    flows = [
        PeriodicFlow(
            id=uuid4(),
            name="Netflix",
            amount=Dezimal("12.99"),
            currency="EUR",
            flow_type=FlowType.EXPENSE,
            frequency=FlowFrequency.MONTHLY,
            category=None,
            enabled=True,
            since=date(2024, 1, 1),
            until=None,
            icon=None,
        )
    ]

    movements = detect_recurring(
        netflix + power + random, set(), today, flows, rate_converter(RATES, "EUR")
    )

    by_key = {m.key: m for m in movements}
    assert set(by_key) == {"netflix com", "iberdrola"}
    fixed = by_key["netflix com"]
    assert fixed.frequency == FlowFrequency.MONTHLY
    assert not fixed.variable
    assert fixed.amount == Dezimal("12.99")
    assert fixed.tracked_flow_id == flows[0].id
    assert fixed.next_date == date(2025, 7, 1)
    variable = by_key["iberdrola"]
    assert variable.variable
    assert variable.max_amount == Dezimal(80)
    assert variable.tracked_flow_id is None


def test_detect_splits_same_name_group_by_amount():
    today = date(2026, 10, 4)
    name = "C. P. ANIT307332-000000352729"
    fee = _monthly(name, ["83.12"] * 6, TxType.OUTFLOW, date(2026, 10, 2))
    extra = [_tx("5", TxType.OUTFLOW, date(2026, 9, 10), name=name)]
    gas = [
        _tx("20", TxType.OUTFLOW, date(2026, 7, 5), name="Gas"),
        _tx("90", TxType.OUTFLOW, date(2026, 8, 3), name="Gas"),
        _tx("35", TxType.OUTFLOW, date(2026, 9, 6), name="Gas"),
        _tx("140", TxType.OUTFLOW, date(2026, 10, 1), name="Gas"),
    ]

    movements = detect_recurring(
        fee + extra + gas, set(), today, [], rate_converter(RATES, "EUR")
    )

    assert len(movements) == 1
    movement = movements[0]
    assert movement.key == "c p anit"
    assert movement.frequency == FlowFrequency.MONTHLY
    assert not movement.variable
    assert movement.amount == Dezimal("83.12")
    assert movement.occurrences == 6


def test_detect_multiple_recurring_amounts_for_same_name():
    today = date(2025, 6, 10)
    basic = _monthly("Apple", ["2.99"] * 4, TxType.OUTFLOW, date(2025, 6, 2))
    music = _monthly("Apple", ["10.99"] * 4, TxType.OUTFLOW, date(2025, 6, 5))

    movements = detect_recurring(
        basic + music, set(), today, [], rate_converter(RATES, "EUR")
    )

    assert sorted(m.amount.val for m in movements) == [
        Dezimal("2.99").val,
        Dezimal("10.99").val,
    ]
    assert all(m.frequency == FlowFrequency.MONTHLY for m in movements)


def test_detect_skips_inactive_and_linked():
    today = date(2025, 12, 1)
    old = _monthly("Gym", ["30"] * 4, TxType.OUTFLOW, date(2025, 6, 1))
    linked = _monthly(
        "Broker", ["100"] * 4, TxType.OUTFLOW, date(2025, 11, 20), linked_tx="x"
    )

    assert (
        detect_recurring(old + linked, set(), today, [], rate_converter(RATES, "EUR"))
        == []
    )


def _flow(name, amount, frequency=FlowFrequency.MONTHLY):
    return PeriodicFlow(
        id=uuid4(),
        name=name,
        amount=Dezimal(amount),
        currency="EUR",
        flow_type=FlowType.EXPENSE,
        frequency=frequency,
        category=None,
        enabled=True,
        since=date(2024, 1, 1),
        until=None,
        icon=None,
    )


def _budget(
    flows,
    txs=None,
    from_date=date(2025, 3, 1),
    to_date=date(2025, 3, 11),
    excluded=None,
    contributions=None,
    investment_txs=None,
    savings_label_ids=None,
    wants_label_ids=None,
):
    excluded = excluded or set()
    convert = rate_converter(RATES, "EUR")
    summary = aggregate_cashflow(
        txs or [],
        [],
        excluded,
        convert,
        CashflowQuery(currency="EUR", from_date=from_date, to_date=to_date),
    )
    return compare_budget(
        flows,
        from_date,
        to_date,
        summary.totals.income,
        summary.totals.expenses,
        {row.label_id: (row.income, row.expenses) for row in summary.by_label},
        excluded,
        convert,
        contributions=contributions,
        investment_txs=investment_txs,
        account_txs=txs or [],
        savings_label_ids=savings_label_ids,
        wants_label_ids=wants_label_ids,
    )


def test_budget_full_targets_with_aggregated_labels_and_overlapping_actuals():
    food, home = uuid4(), uuid4()
    first, second = _flow("Food", "400"), _flow("Food extras", "200")
    first.label_id = second.label_id = food
    salary = _flow("Salary", "2000")
    salary.flow_type = FlowType.EARNING
    result = _budget(
        [first, second, salary],
        [
            _tx("750", TxType.OUTFLOW, date(2025, 3, 5), labels=[food, home]),
            _tx("2100", TxType.INFLOW, date(2025, 3, 1)),
        ],
    )
    assert result.expenses.expected == Dezimal("600")
    assert result.expenses.actual == Dezimal("750")
    assert result.expenses.ratio == Dezimal("1.25")
    assert result.expenses.difference == Dezimal("150")
    assert result.saved.expected == Dezimal("1400")
    assert result.saved.actual == Dezimal("1350")
    rows = {row.label_id: row.comparison for row in result.by_label}
    assert rows[food].expected == Dezimal("600")
    assert rows[food].actual == Dezimal("750")
    assert home not in rows
    assert None not in rows
    assert all(row.flow_type == FlowType.EXPENSE for row in result.by_label)


def test_budget_splits_expense_targets_and_counts_each_movement_once():
    needs, wants, other_wants, excluded = uuid4(), uuid4(), uuid4(), uuid4()
    essential, discretionary = _flow("Rent", "200"), _flow("Leisure", "100")
    essential.label_id = needs
    discretionary.label_id = wants
    ignored = _flow("Transfer", "500")
    ignored.label_id = excluded
    result = _budget(
        [essential, discretionary, _flow("Unassigned", "50"), ignored],
        [
            _tx(
                "-125", TxType.OUTFLOW, date(2025, 3, 5), currency="USD", labels=[needs]
            ),
            _tx("75", TxType.OUTFLOW, date(2025, 3, 5)),
            _tx(
                "80",
                TxType.OUTFLOW,
                date(2025, 3, 5),
                labels=[wants, other_wants, wants],
            ),
            _tx("40", TxType.OUTFLOW, date(2025, 3, 5), labels=[needs, wants]),
            _tx("5", TxType.FEE, date(2025, 3, 5), labels=[other_wants]),
            _tx("1000", TxType.INFLOW, date(2025, 3, 5), labels=[wants]),
            _tx("10", TxType.INTEREST, date(2025, 3, 5), labels=[wants]),
            _tx("500", TxType.OUTFLOW, date(2025, 3, 5), labels=[excluded, wants]),
            _tx(
                "300", TxType.OUTFLOW, date(2025, 3, 5), labels=[needs], linked_tx="buy"
            ),
        ],
        excluded={excluded},
        wants_label_ids={wants, other_wants},
    )

    assert result.needs.expected == Dezimal("250")
    assert result.needs.actual == Dezimal("175")
    assert result.needs.ratio == Dezimal("0.7")
    assert result.needs.difference == Dezimal("-75")
    assert result.wants.expected == Dezimal("100")
    assert result.wants.actual == Dezimal("125")
    assert result.wants.ratio == Dezimal("1.25")
    assert result.wants.difference == Dezimal("25")
    assert result.needs.expected + result.wants.expected == result.expenses.expected
    assert result.needs.actual + result.wants.actual == result.expenses.actual
    assert result.saved.actual == Dezimal("710")
    assert result.invested.actual == 0


def test_budget_spending_split_reconciles_rounded_amounts_to_expense_totals():
    wants = uuid4()
    essential = _flow("Essential", "0.06", FlowFrequency.YEARLY)
    discretionary = _flow("Discretionary", "0.06", FlowFrequency.YEARLY)
    discretionary.label_id = wants
    result = _budget(
        [essential, discretionary],
        [
            _tx("0.03", TxType.OUTFLOW, date(2025, 3, 5), currency="USD"),
            _tx(
                "0.03", TxType.OUTFLOW, date(2025, 3, 5), currency="USD", labels=[wants]
            ),
        ],
        wants_label_ids={wants},
    )

    assert result.expenses.expected == Dezimal("0.01")
    assert result.expenses.actual == Dezimal("0.05")
    assert result.needs.expected + result.wants.expected == result.expenses.expected
    assert result.needs.actual + result.wants.actual == result.expenses.actual


def test_budget_spending_split_uses_exact_activity_dates():
    wants = uuid4()
    result = _budget(
        [],
        [
            _tx("100", TxType.OUTFLOW, date(2025, 3, 2)),
            _tx("50", TxType.OUTFLOW, date(2025, 3, 3)),
            _tx("20", TxType.OUTFLOW, date(2025, 3, 11), labels=[wants]),
            _tx("100", TxType.OUTFLOW, date(2025, 3, 12), labels=[wants]),
        ],
        from_date=date(2025, 3, 3),
        wants_label_ids={wants},
    )

    assert result.needs.actual == Dezimal("50")
    assert result.wants.actual == Dezimal("20")
    assert result.needs.ratio is None
    assert result.wants.ratio is None


@pytest.mark.parametrize("is_wants", [False, True])
def test_budget_spending_targets_keep_full_months_and_currency_conversion(is_wants):
    label_id = uuid4()
    flow = _flow("Budget item", "625")
    flow.label_id = label_id
    flow.currency = "USD"
    flow.since = date(2024, 12, 30)
    flow.until = date(2025, 1, 2)
    result = _budget(
        [flow],
        from_date=date(2024, 12, 31),
        to_date=date(2025, 2, 11),
        wants_label_ids={label_id} if is_wants else set(),
    )

    assert result.needs.expected == (Dezimal(0) if is_wants else Dezimal("1000"))
    assert result.wants.expected == (Dezimal("1000") if is_wants else Dezimal(0))
    flow.enabled = False
    disabled = _budget([flow], wants_label_ids={label_id})
    assert disabled.needs.expected == 0
    assert disabled.wants.expected == 0


@pytest.mark.parametrize("missing_needs", [False, True])
def test_budget_spending_split_keeps_known_actual_when_other_conversion_is_missing(
    missing_needs,
):
    wants = uuid4()
    discretionary = _flow("Leisure", "100")
    discretionary.label_id = wants
    result = _budget(
        [_flow("Rent", "200"), discretionary],
        [
            _tx(
                "50",
                TxType.OUTFLOW,
                date(2025, 3, 5),
                currency="GBP" if missing_needs else "EUR",
            ),
            _tx(
                "25",
                TxType.OUTFLOW,
                date(2025, 3, 5),
                currency="EUR" if missing_needs else "GBP",
                labels=[wants],
            ),
        ],
        wants_label_ids={wants},
    )

    assert result.missing_conversion_count == 1
    assert result.needs.actual == (None if missing_needs else Dezimal("50"))
    assert result.wants.actual == (Dezimal("25") if missing_needs else None)
    assert result.needs.ratio is None
    assert result.wants.ratio is None
    assert result.needs.difference is None
    assert result.wants.difference is None


def _contribution(amount="120", frequency=ContributionFrequency.MONTHLY, **kwargs):
    return PeriodicContribution(
        id=uuid4(),
        alias=None,
        target="Fund",
        target_name="Fund",
        target_type=ContributionTargetType.FUND,
        amount=Dezimal(amount),
        currency="EUR",
        since=date(2024, 1, 1),
        until=None,
        frequency=frequency,
        active=True,
        source=DataSource.REAL,
        **kwargs,
    )


def _investment_tx(
    amount,
    tx_type,
    day=date(2025, 3, 5),
    currency="EUR",
    product_type=ProductType.FUND,
):
    return BaseInvestmentTx(
        id=uuid4(),
        ref=str(uuid4()),
        name="Investment",
        amount=Dezimal(amount),
        currency=currency,
        type=tx_type,
        date=datetime(day.year, day.month, day.day, 12, tzinfo=tzlocal()),
        entity=ENTITY,
        source=DataSource.REAL,
        product_type=product_type,
    )


def test_budget_investing_ignores_deposit_transactions():
    deposit = ProductType.DEPOSIT
    txs = [_tx("1000", TxType.INFLOW, date(2025, 3, 1))]
    convert = rate_converter(RATES, "EUR")
    query = CashflowQuery(
        currency="EUR", from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)
    )
    summary = aggregate_cashflow(txs, [], set(), convert, query)

    result = compare_budget(
        [],
        query.from_date,
        query.to_date,
        summary.totals.income,
        summary.totals.expenses,
        {},
        set(),
        convert,
        investment_txs=[
            _investment_tx("20000", TxType.INVESTMENT, product_type=deposit),
            _investment_tx("15000", TxType.BUY, product_type=deposit),
            _investment_tx("5000", TxType.REPAYMENT, product_type=deposit),
            _investment_tx("300", TxType.BUY),
        ],
        account_txs=txs,
        period_of=lambda day: period_start(day, query.granularity),
        income_by_period={point.period: point.income for point in summary.series},
    )

    assert result.invested.actual == Dezimal("300")
    assert result.invested_breakdown.transactions == Dezimal("300")
    assert [(p.invested, p.remainder) for p in result.series] == [
        (Dezimal(300), Dezimal(700))
    ]


def test_budget_investing_nets_purchases_and_sales_without_reducing_operating_savings():
    salary = _flow("Salary", "2000")
    salary.flow_type = FlowType.EARNING
    result = _budget(
        [salary, _flow("Food", "600")],
        [
            _tx("2100", TxType.INFLOW, date(2025, 3, 1)),
            _tx("750", TxType.OUTFLOW, date(2025, 3, 5)),
            _tx("300", TxType.OUTFLOW, date(2025, 3, 5), linked_tx="buy"),
        ],
        contributions=[_contribution("400")],
        investment_txs=[
            _investment_tx("-300", TxType.BUY),
            _investment_tx("125", TxType.INVESTMENT, currency="USD"),
            _investment_tx("50", TxType.SUBSCRIPTION),
            _investment_tx("200", TxType.SELL),
            _investment_tx("100", TxType.TRANSFER_IN),
            _investment_tx("100", TxType.SWITCH_TO),
            _investment_tx("100", TxType.SWAP_TO),
            _investment_tx("100", TxType.BUY, day=date(2025, 3, 12)),
        ],
    )
    assert result.invested.expected == Dezimal("400")
    assert result.invested.actual == Dezimal("250")
    assert result.invested.ratio == Dezimal("0.625")
    assert result.invested.difference == Dezimal("-150")
    assert result.expenses.actual == Dezimal("750")
    assert result.saved.expected == Dezimal("1400")
    assert result.saved.actual == Dezimal("1350")


def test_budget_investing_combines_savings_labels_with_investment_transactions():
    savings, other_savings, internal_transfer = uuid4(), uuid4(), uuid4()
    result = _budget(
        [],
        [
            _tx("1000", TxType.INFLOW, date(2025, 3, 1)),
            _tx("200", TxType.OUTFLOW, date(2025, 3, 2)),
            _tx(
                "250", TxType.OUTFLOW, date(2025, 3, 3), labels=[savings, other_savings]
            ),
            _tx("50", TxType.INFLOW, date(2025, 3, 4), labels=[savings]),
            _tx(
                "300",
                TxType.OUTFLOW,
                date(2025, 3, 5),
                labels=[savings],
                linked_tx="buy",
            ),
            _tx("400", TxType.OUTFLOW, date(2025, 3, 6), labels=[internal_transfer]),
            _tx("1000", TxType.OUTFLOW, date(2025, 3, 12), labels=[savings]),
        ],
        excluded={savings, other_savings, internal_transfer},
        savings_label_ids={savings, other_savings},
        contributions=[_contribution("500")],
        investment_txs=[
            _investment_tx("300", TxType.BUY),
            _investment_tx("100", TxType.SELL),
        ],
    )

    assert result.invested.expected == Dezimal("500")
    assert result.invested.actual == Dezimal("400")
    assert result.invested.ratio == Dezimal("0.8")
    assert result.invested_breakdown.savings == Dezimal("200")
    assert result.invested_breakdown.transactions == Dezimal("200")
    assert result.saved.actual == Dezimal("800")
    assert result.expenses.actual == Dezimal("200")


def test_budget_series_splits_each_period_into_needs_wants_invested_and_remainder():
    savings, wants = uuid4(), uuid4()
    txs = [
        _tx("1000", TxType.INFLOW, date(2025, 3, 1)),
        _tx("300", TxType.OUTFLOW, date(2025, 3, 2)),
        _tx("100", TxType.OUTFLOW, date(2025, 3, 3), labels=[wants]),
        _tx("200", TxType.OUTFLOW, date(2025, 3, 4), labels=[savings]),
        _tx("400", TxType.OUTFLOW, date(2025, 3, 5), linked_tx="buy"),
        _tx("50", TxType.OUTFLOW, date(2025, 4, 2), labels=[wants]),
        _tx("25", TxType.OUTFLOW, date(2025, 4, 3), currency="GBP"),
    ]
    convert = rate_converter(RATES, "EUR")
    query = CashflowQuery(
        currency="EUR", from_date=date(2025, 3, 1), to_date=date(2025, 5, 31)
    )
    summary = aggregate_cashflow(txs, [], {savings}, convert, query)

    result = compare_budget(
        [],
        query.from_date,
        query.to_date,
        summary.totals.income,
        summary.totals.expenses,
        {},
        {savings},
        convert,
        investment_txs=[
            _investment_tx("400", TxType.BUY),
            _investment_tx("150", TxType.SELL, day=date(2025, 5, 10)),
        ],
        account_txs=txs,
        savings_label_ids={savings},
        wants_label_ids={wants},
        period_of=lambda day: period_start(day, query.granularity),
        income_by_period={point.period: point.income for point in summary.series},
    )

    assert [
        (p.period, p.needs, p.wants, p.invested, p.remainder) for p in result.series
    ] == [
        (date(2025, 3, 1), Dezimal(300), Dezimal(100), Dezimal(600), Dezimal(0)),
        (date(2025, 4, 1), Dezimal(0), Dezimal(50), Dezimal(0), Dezimal(-50)),
        (date(2025, 5, 1), Dezimal(0), Dezimal(0), Dezimal(-150), Dezimal(150)),
    ]
    assert _budget([], txs).series == []


@pytest.mark.parametrize("missing_savings", [True, False])
def test_budget_combined_investing_missing_conversion_preserves_known_subtotal(
    missing_savings,
):
    savings = uuid4()
    result = _budget(
        [],
        [
            _tx(
                "150",
                TxType.OUTFLOW,
                date(2025, 3, 5),
                currency="GBP" if missing_savings else "EUR",
                labels=[savings],
            )
        ],
        excluded={savings},
        savings_label_ids={savings},
        investment_txs=[
            _investment_tx(
                "300", TxType.BUY, currency="EUR" if missing_savings else "GBP"
            )
        ],
    )

    assert result.missing_conversion_count == 1
    assert result.invested.actual is None
    assert result.invested.ratio is None
    assert result.invested.difference is None
    assert result.invested_breakdown.savings == (
        None if missing_savings else Dezimal("150")
    )
    assert result.invested_breakdown.transactions == (
        Dezimal("300") if missing_savings else None
    )


def test_budget_combined_investing_sums_displayed_converted_subtotals():
    savings = uuid4()
    result = _budget(
        [],
        [
            _tx(
                "0.03",
                TxType.OUTFLOW,
                date(2025, 3, 5),
                currency="USD",
                labels=[savings],
            )
        ],
        excluded={savings},
        savings_label_ids={savings},
        investment_txs=[_investment_tx("0.03", TxType.BUY, currency="USD")],
    )

    assert result.invested_breakdown.savings == Dezimal("0.02")
    assert result.invested_breakdown.transactions == Dezimal("0.02")
    assert result.invested.actual == Dezimal("0.04")


def test_budget_savings_allocation_excludes_interest_and_fees():
    savings = uuid4()
    result = _budget(
        [],
        [
            _tx("30", TxType.INTEREST, date(2025, 3, 5), labels=[savings]),
            _tx("5", TxType.FEE, date(2025, 3, 5), labels=[savings]),
        ],
        excluded={savings},
        savings_label_ids={savings},
    )

    assert result.invested.actual == 0
    assert result.invested_breakdown.savings == 0


def test_budget_investing_does_not_count_reinvested_sale_proceeds_twice():
    result = _budget(
        [],
        contributions=[_contribution("500")],
        investment_txs=[
            _investment_tx("-500", TxType.BUY),
            _investment_tx("500", TxType.SELL),
            _investment_tx("500", TxType.BUY),
        ],
    )

    assert result.invested.expected == Dezimal("500")
    assert result.invested.actual == Dezimal("500")
    assert result.invested.ratio == Dezimal(1)
    assert result.invested.difference == Dezimal(0)


@pytest.mark.parametrize("tx_type", [TxType.SELL, TxType.REPAYMENT])
@pytest.mark.parametrize("amount", ["100", "-100"])
def test_budget_investing_subtracts_returns_regardless_of_amount_sign(tx_type, amount):
    result = _budget(
        [],
        contributions=[_contribution("500")],
        investment_txs=[
            _investment_tx("-300", TxType.BUY),
            _investment_tx(amount, tx_type, day=date(2025, 3, 11)),
            _investment_tx("1000", tx_type, day=date(2025, 3, 12)),
        ],
    )

    assert result.invested.actual == Dezimal("200")
    assert result.invested.ratio == Dezimal("0.4")
    assert result.invested.difference == Dezimal("-300")


@pytest.mark.parametrize("tx_type", [TxType.SELL, TxType.REPAYMENT])
def test_budget_investing_converts_returns_and_preserves_negative_net(tx_type):
    result = _budget(
        [],
        contributions=[_contribution("100")],
        investment_txs=[
            _investment_tx("50", TxType.BUY),
            _investment_tx("125", tx_type, currency="USD"),
        ],
    )

    assert result.invested.actual == Dezimal("-50")
    assert result.invested.ratio == Dezimal("-0.5")
    assert result.invested.difference == Dezimal("-150")


@pytest.mark.parametrize("frequency", list(ContributionFrequency))
def test_budget_investment_targets_support_all_contribution_frequencies(frequency):
    result = _budget([], contributions=[_contribution(frequency=frequency)])
    assert result.invested.expected == round(
        Dezimal("120") * CONTRIBUTION_MONTHLY_MULTIPLIERS[frequency], 2
    )
    assert result.entry_count == 1


def test_budget_investment_targets_count_full_active_months():
    contribution = _contribution()
    contribution.since = date(2024, 12, 30)
    contribution.until = date(2025, 1, 2)
    result = _budget(
        [],
        from_date=date(2024, 12, 31),
        to_date=date(2025, 2, 11),
        contributions=[contribution],
    )
    assert result.invested.expected == Dezimal("240")
    contribution.active = False
    assert _budget([], contributions=[contribution]).invested.expected == 0


@pytest.mark.parametrize("tx_type", [TxType.BUY, TxType.SELL, TxType.REPAYMENT])
def test_budget_investment_missing_conversion_is_not_reported_as_zero_actual(tx_type):
    result = _budget(
        [],
        contributions=[_contribution()],
        investment_txs=[_investment_tx("100", tx_type, currency="GBP")],
    )
    assert result.missing_conversion_count == 1
    assert result.invested.expected == Dezimal("120")
    assert result.invested.actual is None
    assert result.invested.ratio is None
    assert result.invested.difference is None


def test_budget_targets_count_full_active_months_across_year_boundary():
    flow = _flow("Rent", "600")
    flow.since = date(2024, 12, 30)
    flow.until = date(2025, 1, 2)
    result = _budget([flow], from_date=date(2024, 12, 31), to_date=date(2025, 2, 11))
    assert result.expenses.expected == Dezimal("1200")
    assert result.from_month == date(2024, 12, 1)
    assert result.to_month == date(2025, 2, 1)
    flow.enabled = False
    assert target_months(flow, date(2024, 12, 1), date(2025, 2, 11)) == 0


@pytest.mark.parametrize("frequency", list(FlowFrequency))
def test_budget_supports_all_frequency_monthly_equivalents(frequency):
    flow = _flow("Allocation", "120", frequency)
    result = _budget([flow])
    assert result.expenses.expected == round(
        Dezimal("120") * MONTHLY_MULTIPLIERS[frequency], 2
    )


def test_budget_zero_and_negative_saved_targets_have_no_ratio():
    result = _budget([_flow("Rent", "600")])
    assert result.income.ratio is None
    assert result.saved.expected == Dezimal("-600")
    assert result.saved.ratio is None
    assert result.saved.difference == Dezimal("600")


def test_budget_saved_target_subtracts_the_displayed_monetary_targets():
    income = _flow("Annual income", "0.18", FlowFrequency.YEARLY)
    income.flow_type = FlowType.EARNING
    expense = _flow("Annual expense", "0.06", FlowFrequency.YEARLY)
    result = _budget([income, expense])
    assert result.income.expected == Dezimal("0.02")
    assert result.expenses.expected == Dezimal("0.00")
    assert result.saved.expected == result.income.expected - result.expenses.expected


def test_budget_converts_targets_and_retains_signed_negative_actual_saved():
    income = _flow("Salary", "2000")
    income.flow_type = FlowType.EARNING
    expense = _flow("Rent", "625")
    expense.currency = "USD"
    result = _budget(
        [income, expense],
        [_tx("2100", TxType.OUTFLOW, date(2025, 3, 3))],
    )
    assert result.expenses.expected == Dezimal("500")
    assert result.saved.expected == Dezimal("1500")
    assert result.saved.actual == Dezimal("-2100")
    assert result.saved.ratio == Dezimal("-1.4")


def test_budget_missing_rates_suppress_incomplete_ratios_and_differences():
    flow = _flow("Food", "600")
    unknown = _flow("Rent", "100")
    unknown.currency = "GBP"
    result = _budget([flow, unknown])
    assert result.missing_conversion_count == 1
    assert result.entry_count == 2
    assert result.expenses.expected == Dezimal("600")
    assert result.expenses.ratio is None
    assert result.expenses.difference is None


def test_budget_excludes_reclassified_labels_and_investment_cash_legs():
    excluded_id = uuid4()
    flow = _flow("Transfer", "600")
    flow.label_id = excluded_id
    result = _budget(
        [flow],
        [_tx("300", TxType.OUTFLOW, date(2025, 3, 5), linked_tx="investment")],
        excluded={excluded_id},
    )
    assert result.entry_count == 0
    assert result.expenses.expected == 0
    assert result.expenses.actual == 0


def _tracked(movements, key):
    return next(m for m in movements if m.key == key).tracked_flow_id


def test_tracked_flow_prefers_closest_amount_and_ignores_distant_unnamed():
    today = date(2025, 6, 10)
    loan = _monthly(
        "AMORTIZACION PRESTAMO", ["480"] * 4, TxType.OUTFLOW, date(2025, 6, 1)
    )
    rent_flow = _flow("Rent", "574.10")
    mortgage_flow = _flow("Mortgage", "480")

    movements = detect_recurring(
        loan, set(), today, [rent_flow, mortgage_flow], rate_converter(RATES, "EUR")
    )
    assert _tracked(movements, "amortizacion prestamo") == mortgage_flow.id

    movements = detect_recurring(
        loan, set(), today, [rent_flow], rate_converter(RATES, "EUR")
    )
    assert _tracked(movements, "amortizacion prestamo") is None


def test_tracked_flow_allows_wider_amount_on_name_match_and_is_one_to_one():
    today = date(2025, 6, 10)
    gym = _monthly("GYM CENTER", ["45"] * 4, TxType.OUTFLOW, date(2025, 6, 2))
    other = _monthly("CLUB", ["40"] * 4, TxType.OUTFLOW, date(2025, 6, 4))
    gym_flow = _flow("Gym", "40")

    movements = detect_recurring(
        gym + other, set(), today, [gym_flow], rate_converter(RATES, "EUR")
    )

    assert _tracked(movements, "gym center") == gym_flow.id
    assert _tracked(movements, "club") is None


def test_ignored_movement_matches_same_series_within_amount_band():
    today = date(2025, 6, 10)
    basic = _monthly("Apple", ["2.99"] * 4, TxType.OUTFLOW, date(2025, 6, 2))
    music = _monthly("Apple", ["10.99"] * 4, TxType.OUTFLOW, date(2025, 6, 5))
    ignored = IgnoredRecurringMovement(
        id=uuid4(),
        key="apple",
        type=TxType.OUTFLOW,
        currency="eur",
        amount=Dezimal("9.99"),
    )

    movements = detect_recurring(
        basic + music,
        set(),
        today,
        [],
        rate_converter(RATES, "EUR"),
        [ignored],
    )

    by_amount = {m.amount.val: m for m in movements}
    assert by_amount[Dezimal("10.99").val].ignored_id == ignored.id
    assert by_amount[Dezimal("2.99").val].ignored_id is None


def test_ignored_movement_matches_key_truncated_at_a_space():
    name = (
        "IMPUESTO DE RENTAS DE CAPITAL (I.R.C) REMUNERACIÓN CAP. SOCIAL "
        "LIQ SEMESTR SOCIO: 0002310847"
    )
    txs = _monthly(name, ["0.11"] * 4, TxType.OUTFLOW, date(2025, 6, 2))
    ignored = IgnoredRecurringMovement(
        id=uuid4(),
        key="impuesto de rentas de capital i r c remuneracion cap social",
        type=TxType.OUTFLOW,
        currency="EUR",
        amount=Dezimal("0.11"),
    )

    movements = detect_recurring(
        txs, set(), date(2025, 6, 10), [], rate_converter(RATES, "EUR"), [ignored]
    )

    assert [m.key for m in movements] == [ignored.key]
    assert movements[0].ignored_id == ignored.id


def test_ignored_movement_is_not_matched_to_tracked_flows():
    today = date(2025, 6, 10)
    gym = _monthly("GYM CENTER", ["45"] * 4, TxType.OUTFLOW, date(2025, 6, 2))
    gym_flow = _flow("Gym", "45")
    ignored = IgnoredRecurringMovement(
        id=uuid4(),
        key="gym center",
        type=TxType.OUTFLOW,
        currency="EUR",
        amount=Dezimal("45"),
    )

    movements = detect_recurring(
        gym, set(), today, [gym_flow], rate_converter(RATES, "EUR"), [ignored]
    )

    assert movements[0].ignored_id == ignored.id
    assert movements[0].tracked_flow_id is None
