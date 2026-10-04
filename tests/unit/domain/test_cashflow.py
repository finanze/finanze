from datetime import date, datetime, timedelta
from uuid import uuid4

from dateutil.tz import tzlocal

from domain.cashflow import (
    CashflowGranularity,
    CashflowQuery,
    IgnoredRecurringMovement,
    aggregate_cashflow,
    detect_recurring,
    previous_period,
    rate_converter,
)
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.transactions import AccountTx, LabelOrigin, TxLabel, TxType

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
    assert [(p.period, p.income, p.expenses) for p in summary.series] == [
        (date(2025, 3, 1), Dezimal(2000), Dezimal(100)),
        (date(2025, 4, 1), Dezimal(0), Dezimal(60)),
    ]
    by_label = {b.label_id: b for b in summary.by_label}
    assert by_label[groceries].expenses == Dezimal(150)
    assert by_label[None].income == Dezimal(2000)
    assert summary.top_counterparties[0].name == "Payroll"


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
