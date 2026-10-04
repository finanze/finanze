import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from enum import Enum
from statistics import median_low
from typing import Callable, Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.exchange_rate import ExchangeRates
from domain.labeling import normalize_text
from domain.transactions import (
    ACCOUNT_INCOMING_TYPES,
    ACCOUNT_MOVEMENT_TYPES,
    AccountTx,
    TxType,
)
from pydantic.dataclasses import dataclass

CASHFLOW_TX_TYPES = [TxType.INFLOW, TxType.OUTFLOW, TxType.INTEREST, TxType.FEE]
DEFAULT_TOP_COUNTERPARTIES = 10
DEFAULT_RECURRING_LOOKBACK_MONTHS = 24
MAX_RECURRING_LOOKBACK_MONTHS = 36

FIXED_AMOUNT_DEVIATION = Dezimal("0.15")
VARIABLE_AMOUNT_DEVIATION = Dezimal("0.5")
TRACKED_AMOUNT_TOLERANCE = Dezimal("0.05")
TRACKED_NAMED_AMOUNT_TOLERANCE = Dezimal("0.25")
AVERAGE_MONTH_DAYS = Dezimal("30.44")

# (frequency, expected days between occurrences, tolerance in days)
RECURRING_FREQUENCIES = [
    (FlowFrequency.WEEKLY, 7, 2),
    (FlowFrequency.BIWEEKLY, 14, 3),
    (FlowFrequency.MONTHLY, 30, 5),
    (FlowFrequency.EVERY_TWO_MONTHS, 61, 8),
    (FlowFrequency.QUARTERLY, 91, 12),
    (FlowFrequency.EVERY_FOUR_MONTHS, 122, 14),
    (FlowFrequency.SEMIANNUALLY, 183, 18),
    (FlowFrequency.YEARLY, 365, 25),
]

Converter = Callable[[Dezimal, str], Optional[Dezimal]]


class CashflowGranularity(str, Enum):
    DAY = "DAY"
    MONTH = "MONTH"


@dataclass
class CashflowQuery:
    currency: str
    from_date: date
    to_date: date
    entities: Optional[list[UUID]] = None
    granularity: CashflowGranularity = CashflowGranularity.MONTH


@dataclass
class CashflowTotals:
    income: Dezimal
    expenses: Dezimal
    net: Dezimal
    count: int
    savings_rate: Optional[Dezimal] = None


@dataclass
class CashflowPoint:
    period: date
    income: Dezimal
    expenses: Dezimal


@dataclass
class CashflowLabelBreakdown:
    label_id: Optional[UUID]
    income: Dezimal
    expenses: Dezimal
    count: int


@dataclass
class CashflowCounterparty:
    name: str
    income: Dezimal
    expenses: Dezimal
    count: int


@dataclass
class CashflowSummary:
    currency: str
    from_date: date
    to_date: date
    totals: CashflowTotals
    previous: CashflowTotals
    series: list[CashflowPoint]
    by_label: list[CashflowLabelBreakdown]
    top_counterparties: list[CashflowCounterparty]
    excluded_count: int = 0


@dataclass
class RecurringMovementsQuery:
    currency: str
    lookback_months: int = DEFAULT_RECURRING_LOOKBACK_MONTHS
    entities: Optional[list[UUID]] = None
    type: Optional[TxType] = None


@dataclass
class RecurringMovement:
    key: str
    name: str
    search: str
    type: TxType
    currency: str
    amount: Dezimal
    average_amount: Dezimal
    max_amount: Dezimal
    variable: bool
    frequency: FlowFrequency
    occurrences: int
    first_date: date
    last_date: date
    next_date: date
    label_ids: list[UUID]
    entity_ids: list[UUID]
    monthly_amount: Optional[Dezimal] = None
    tracked_flow_id: Optional[UUID] = None
    ignored_id: Optional[UUID] = None


@dataclass
class IgnoredRecurringMovement:
    key: str
    type: TxType
    currency: str
    amount: Dezimal
    id: Optional[UUID] = None


@dataclass
class RecurringMovements:
    currency: str
    movements: list[RecurringMovement]


def rate_converter(rates: ExchangeRates, target_currency: str) -> Converter:
    target = target_currency.upper()
    quotes = rates.get(target) or {}

    def convert(amount: Dezimal, currency: str) -> Optional[Dezimal]:
        source = (currency or target).upper()
        if source == target:
            return amount
        rate = quotes.get(source)
        if rate is None or rate == 0:
            return None
        return amount / rate

    return convert


def previous_period(from_date: date, to_date: date) -> tuple[date, date]:
    length = (to_date - from_date).days + 1
    previous_to = from_date - timedelta(days=1)
    return previous_to - timedelta(days=length - 1), previous_to


def is_income(tx: AccountTx) -> bool:
    return tx.type in ACCOUNT_INCOMING_TYPES


def cashflow_amount(tx: AccountTx) -> Dezimal:
    if tx.type != TxType.INTEREST:
        return abs(tx.amount)
    if tx.net_amount is not None:
        return abs(tx.net_amount)
    return abs(tx.amount) - abs(tx.retentions) - abs(tx.fees)


def is_counted(tx: AccountTx, excluded_label_ids: set[UUID]) -> bool:
    if tx.type not in CASHFLOW_TX_TYPES or tx.linked_tx:
        return False
    return not any(label.label_id in excluded_label_ids for label in tx.labels or [])


def counterparty_key(tx: AccountTx) -> str:
    text = normalize_text(tx.counterparty or tx.name)
    text = re.sub(r"[0-9]+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())[:60]


def _display_name(tx: AccountTx) -> str:
    return " ".join((tx.counterparty or tx.name or "").split())


def _period_start(day: date, granularity: CashflowGranularity) -> date:
    if granularity == CashflowGranularity.DAY:
        return day
    return day.replace(day=1)


def _totals(income: Dezimal, expenses: Dezimal, count: int) -> CashflowTotals:
    net = income - expenses
    savings_rate = round(net / income, 4) if income > 0 else None
    return CashflowTotals(
        income=round(income, 2),
        expenses=round(expenses, 2),
        net=round(net, 2),
        count=count,
        savings_rate=savings_rate,
    )


def summarize_totals(
    txs: list[AccountTx], excluded_label_ids: set[UUID], convert: Converter
) -> CashflowTotals:
    income, expenses, count = Dezimal(0), Dezimal(0), 0
    for tx in txs:
        if not is_counted(tx, excluded_label_ids):
            continue
        amount = convert(cashflow_amount(tx), tx.currency)
        if amount is None:
            continue
        count += 1
        if is_income(tx):
            income += amount
        else:
            expenses += amount
    return _totals(income, expenses, count)


def aggregate_cashflow(
    txs: list[AccountTx],
    previous_txs: list[AccountTx],
    excluded_label_ids: set[UUID],
    convert: Converter,
    query: CashflowQuery,
    top_counterparties: int = DEFAULT_TOP_COUNTERPARTIES,
) -> CashflowSummary:
    income, expenses, count, excluded = Dezimal(0), Dezimal(0), 0, 0
    series: dict[date, list[Dezimal]] = {}
    by_label: dict[Optional[UUID], list] = {}
    counterparties: dict[str, dict] = {}

    for tx in txs:
        if not is_counted(tx, excluded_label_ids):
            excluded += 1
            continue
        amount = convert(cashflow_amount(tx), tx.currency)
        if amount is None:
            excluded += 1
            continue

        incoming = is_income(tx)
        count += 1
        if incoming:
            income += amount
        else:
            expenses += amount

        period = _period_start(tx.date.date(), query.granularity)
        point = series.setdefault(period, [Dezimal(0), Dezimal(0)])
        point[0 if incoming else 1] += amount

        label_ids = list(dict.fromkeys(label.label_id for label in tx.labels or []))
        for label_id in label_ids or [None]:
            bucket = by_label.setdefault(label_id, [Dezimal(0), Dezimal(0), 0])
            bucket[0 if incoming else 1] += amount
            bucket[2] += 1

        key = counterparty_key(tx)
        if key:
            entry = counterparties.setdefault(
                key,
                {
                    "names": Counter(),
                    "income": Dezimal(0),
                    "expenses": Dezimal(0),
                    "count": 0,
                },
            )
            entry["names"][_display_name(tx)] += 1
            entry["income" if incoming else "expenses"] += amount
            entry["count"] += 1

    points = [
        CashflowPoint(
            period=period, income=round(values[0], 2), expenses=round(values[1], 2)
        )
        for period, values in sorted(series.items())
    ]
    labels = sorted(
        (
            CashflowLabelBreakdown(
                label_id=label_id,
                income=round(values[0], 2),
                expenses=round(values[1], 2),
                count=values[2],
            )
            for label_id, values in by_label.items()
        ),
        key=lambda b: (b.income + b.expenses).val,
        reverse=True,
    )
    top = sorted(
        (
            CashflowCounterparty(
                name=entry["names"].most_common(1)[0][0],
                income=round(entry["income"], 2),
                expenses=round(entry["expenses"], 2),
                count=entry["count"],
            )
            for entry in counterparties.values()
        ),
        key=lambda c: (c.income + c.expenses).val,
        reverse=True,
    )[:top_counterparties]

    return CashflowSummary(
        currency=query.currency,
        from_date=query.from_date,
        to_date=query.to_date,
        totals=_totals(income, expenses, count),
        previous=summarize_totals(previous_txs, excluded_label_ids, convert),
        series=points,
        by_label=labels,
        top_counterparties=top,
        excluded_count=excluded,
    )


def _match_frequency(interval: int):
    for frequency, expected, tolerance in RECURRING_FREQUENCIES:
        if abs(interval - expected) <= tolerance:
            return frequency, expected, tolerance
    return None


def _similar_names(first: str, second: str) -> bool:
    if not first or not second:
        return False
    return first in second or second in first


def _tracked_flow_score(
    movement: RecurringMovement, flow: PeriodicFlow
) -> Optional[tuple[int, Dezimal]]:
    flow_type = FlowType.EARNING if movement.type == TxType.INFLOW else FlowType.EXPENSE
    if flow.id is None or not flow.enabled or flow.flow_type != flow_type:
        return None
    if flow.currency.upper() != movement.currency.upper():
        return None
    flow_amount = abs(flow.amount)
    if flow_amount == 0:
        return None
    distance = abs(flow_amount - movement.amount) / flow_amount
    names_match = _similar_names(
        " ".join(normalize_text(flow.name).split()), movement.key
    )
    if names_match:
        tolerance = TRACKED_NAMED_AMOUNT_TOLERANCE
    elif flow.frequency == movement.frequency:
        tolerance = TRACKED_AMOUNT_TOLERANCE
    else:
        return None
    if distance > tolerance:
        return None
    return (0 if names_match else 1, distance)


def _assign_tracked_flows(
    movements: list[RecurringMovement], flows: list[PeriodicFlow]
) -> None:
    candidates = []
    for index, movement in enumerate(movements):
        for flow in flows:
            score = _tracked_flow_score(movement, flow)
            if score is not None:
                candidates.append((score[0], score[1].val, index, flow.id))
    candidates.sort(key=lambda candidate: candidate[:2])

    matched_movements: set[int] = set()
    matched_flows: set[UUID] = set()
    for _, _, index, flow_id in candidates:
        if index in matched_movements or flow_id in matched_flows:
            continue
        movements[index].tracked_flow_id = flow_id
        matched_movements.add(index)
        matched_flows.add(flow_id)


def detect_recurring(
    txs: list[AccountTx],
    excluded_label_ids: set[UUID],
    today: date,
    flows: list[PeriodicFlow],
    convert: Converter,
    ignored: Optional[list[IgnoredRecurringMovement]] = None,
) -> list[RecurringMovement]:
    groups: dict[tuple[str, TxType, str], list[AccountTx]] = defaultdict(list)
    for tx in txs:
        if tx.type not in ACCOUNT_MOVEMENT_TYPES or not is_counted(
            tx, excluded_label_ids
        ):
            continue
        key = counterparty_key(tx)
        if not key:
            continue
        groups[(key, tx.type, tx.currency.upper())].append(tx)

    movements = []
    for (key, tx_type, currency), group in groups.items():
        movement = _detect_group(key, tx_type, currency, group, today)
        if movement is not None:
            movements.append(movement)
            continue
        clusters = _amount_clusters(group)
        if len(clusters) < 2:
            continue
        for cluster in clusters:
            movement = _detect_group(key, tx_type, currency, cluster, today)
            if movement is not None:
                movements.append(movement)

    for movement in movements:
        match = next(
            (entry for entry in ignored or [] if _matches_ignored(movement, entry)),
            None,
        )
        if match is not None:
            movement.ignored_id = match.id

    _assign_tracked_flows([m for m in movements if m.ignored_id is None], flows)
    for movement in movements:
        movement.monthly_amount = convert(movement.monthly_amount, movement.currency)

    return sorted(
        movements,
        key=lambda m: m.monthly_amount.val if m.monthly_amount is not None else 0,
        reverse=True,
    )


def _matches_ignored(
    movement: RecurringMovement, entry: IgnoredRecurringMovement
) -> bool:
    if (movement.key, movement.type, movement.currency) != (
        entry.key,
        entry.type,
        entry.currency.upper(),
    ):
        return False
    low = min(movement.amount, entry.amount, key=lambda a: a.val)
    high = max(movement.amount, entry.amount, key=lambda a: a.val)
    return high <= low * (Dezimal(1) + VARIABLE_AMOUNT_DEVIATION)


def _amount_clusters(group: list[AccountTx]) -> list[list[AccountTx]]:
    max_step = Dezimal(1) + VARIABLE_AMOUNT_DEVIATION
    ordered = sorted(
        ((cashflow_amount(tx), tx) for tx in group), key=lambda item: item[0].val
    )
    clusters: list[list[AccountTx]] = []
    previous: Optional[Dezimal] = None
    for amount, tx in ordered:
        if previous is None or amount > previous * max_step:
            clusters.append([])
        clusters[-1].append(tx)
        previous = amount
    return clusters


def _detect_group(
    key: str, tx_type: TxType, currency: str, group: list[AccountTx], today: date
) -> Optional[RecurringMovement]:
    if len(group) < 2:
        return None
    group = sorted(group, key=lambda tx: tx.date.date())
    dates = [tx.date.date() for tx in group]
    intervals = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
    if not intervals:
        return None

    matched = _match_frequency(median_low(intervals))
    if matched is None:
        return None
    frequency, expected, tolerance = matched

    min_occurrences = 3 if expected <= 31 else 2
    if len(group) < min_occurrences:
        return None

    regular = [i for i in intervals if abs(i - expected) <= tolerance * 2]
    if len(regular) * 4 < len(intervals) * 3:
        return None

    last_date = dates[-1]
    if (today - last_date).days * 2 > expected * 3 + tolerance * 2:
        return None

    amounts = [cashflow_amount(tx) for tx in group]
    median_amount = Dezimal(median_low(a.val for a in amounts))
    if median_amount <= 0:
        return None
    max_amount = max(amounts, key=lambda a: a.val)
    deviation = max(abs(a - median_amount) for a in amounts) / median_amount
    if deviation > VARIABLE_AMOUNT_DEVIATION:
        return None
    variable = deviation > FIXED_AMOUNT_DEVIATION
    average_amount = sum(amounts, Dezimal(0)) / len(amounts)
    amount = round(average_amount if variable else median_amount, 2)

    label_counter = Counter(
        label_id
        for tx in group
        for label_id in {label.label_id for label in tx.labels or []}
    )
    label_ids = [
        label_id
        for label_id, occurrences in label_counter.most_common()
        if occurrences * 2 >= len(group)
    ]
    names = Counter(_display_name(tx) for tx in group)
    name = names.most_common(1)[0][0]

    return RecurringMovement(
        key=key,
        name=name,
        search=(group[-1].counterparty or group[-1].name or name).strip(),
        type=tx_type,
        currency=currency,
        amount=amount,
        average_amount=round(average_amount, 2),
        max_amount=round(max_amount, 2),
        variable=variable,
        frequency=frequency,
        occurrences=len(group),
        first_date=dates[0],
        last_date=last_date,
        next_date=last_date + timedelta(days=expected),
        label_ids=label_ids,
        entity_ids=list(dict.fromkeys(tx.entity.id for tx in group)),
        monthly_amount=round(amount * AVERAGE_MONTH_DAYS / expected, 2),
    )
