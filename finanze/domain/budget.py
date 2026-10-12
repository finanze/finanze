from dataclasses import field
from datetime import date
from typing import Callable, Optional
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.auto_contributions import ContributionFrequency, PeriodicContribution
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.transactions import AccountTx, BaseInvestmentTx, TxType

MONTHLY_MULTIPLIERS = {
    FlowFrequency.DAILY: Dezimal("30"),
    FlowFrequency.WEEKLY: Dezimal("4.33"),
    FlowFrequency.BIWEEKLY: Dezimal(26) / Dezimal(12),
    FlowFrequency.SEMIMONTHLY: Dezimal("2"),
    FlowFrequency.MONTHLY: Dezimal("1"),
    FlowFrequency.EVERY_TWO_MONTHS: Dezimal(1) / Dezimal(2),
    FlowFrequency.QUARTERLY: Dezimal(1) / Dezimal(3),
    FlowFrequency.EVERY_FOUR_MONTHS: Dezimal(1) / Dezimal(4),
    FlowFrequency.SEMIANNUALLY: Dezimal(1) / Dezimal(6),
    FlowFrequency.YEARLY: Dezimal(1) / Dezimal(12),
}

CONTRIBUTION_MONTHLY_MULTIPLIERS = {
    ContributionFrequency.WEEKLY: Dezimal(52) / Dezimal(12),
    ContributionFrequency.BIWEEKLY: Dezimal(26) / Dezimal(12),
    ContributionFrequency.MONTHLY: Dezimal(1),
    ContributionFrequency.BIMONTHLY: Dezimal(1) / Dezimal(2),
    ContributionFrequency.EVERY_FOUR_MONTHS: Dezimal(1) / Dezimal(4),
    ContributionFrequency.QUARTERLY: Dezimal(1) / Dezimal(3),
    ContributionFrequency.SEMIANNUAL: Dezimal(1) / Dezimal(6),
    ContributionFrequency.YEARLY: Dezimal(1) / Dezimal(12),
}

INVESTMENT_DIRECTIONS = {
    TxType.BUY: 1,
    TxType.INVESTMENT: 1,
    TxType.SUBSCRIPTION: 1,
    TxType.SELL: -1,
    TxType.REPAYMENT: -1,
}


@dataclass
class BudgetComparison:
    expected: Dezimal
    actual: Optional[Dezimal]
    ratio: Optional[Dezimal]
    difference: Optional[Dezimal]


@dataclass
class BudgetLabelComparison:
    label_id: Optional[UUID]
    flow_type: FlowType
    comparison: BudgetComparison


@dataclass
class BudgetInvestmentBreakdown:
    savings: Optional[Dezimal]
    transactions: Optional[Dezimal]


@dataclass
class BudgetPoint:
    period: date
    needs: Dezimal
    wants: Dezimal
    invested: Dezimal
    remainder: Dezimal


@dataclass
class BudgetSummary:
    from_month: date
    to_month: date
    entry_count: int
    missing_conversion_count: int
    income: BudgetComparison
    expenses: BudgetComparison
    needs: BudgetComparison
    wants: BudgetComparison
    saved: BudgetComparison
    invested: BudgetComparison
    by_label: list[BudgetLabelComparison]
    invested_breakdown: BudgetInvestmentBreakdown
    series: list[BudgetPoint] = field(default_factory=list)


def _month_index(day: date) -> int:
    return day.year * 12 + day.month


def target_months(
    flow: PeriodicFlow | PeriodicContribution, from_date: date, to_date: date
) -> int:
    enabled = flow.enabled if isinstance(flow, PeriodicFlow) else flow.active
    if not enabled or (flow.until and flow.until < flow.since):
        return 0
    start = max(_month_index(from_date), _month_index(flow.since))
    end = min(
        _month_index(to_date),
        _month_index(flow.until) if flow.until else _month_index(to_date),
    )
    return max(end - start + 1, 0)


def _comparison(
    expected: Dezimal, actual: Optional[Dezimal], complete: bool
) -> BudgetComparison:
    expected = round(expected, 2)
    actual = round(actual, 2) if actual is not None else None
    return BudgetComparison(
        expected=expected,
        actual=actual,
        ratio=round(actual / expected, 4)
        if complete and actual is not None and expected > 0
        else None,
        difference=round(actual - expected, 2)
        if complete and actual is not None
        else None,
    )


def compare_budget(
    flows: list[PeriodicFlow],
    from_date: date,
    to_date: date,
    actual_income: Dezimal,
    actual_expenses: Dezimal,
    actual_by_label: dict[Optional[UUID], tuple[Dezimal, Dezimal]],
    excluded_label_ids: set[UUID],
    convert: Callable[[Dezimal, str], Optional[Dezimal]],
    *,
    actual_saved: Optional[Dezimal] = None,
    contributions: Optional[list[PeriodicContribution]] = None,
    investment_txs: Optional[list[BaseInvestmentTx]] = None,
    account_txs: Optional[list[AccountTx]] = None,
    savings_label_ids: Optional[set[UUID]] = None,
    wants_label_ids: Optional[set[UUID]] = None,
    period_of: Optional[Callable[[date], date]] = None,
    income_by_period: Optional[dict[date, Dezimal]] = None,
) -> BudgetSummary:
    periods: dict[date, list[Dezimal]] = {}

    def track(day: date, index: int, amount: Dezimal) -> None:
        if period_of is None:
            return
        bucket = periods.setdefault(period_of(day), [Dezimal(0)] * 3)
        bucket[index] += amount

    expected_income, expected_expenses = Dezimal(0), Dezimal(0)
    expected_wants = Dezimal(0)
    expected_by_label: dict[tuple[Optional[UUID], FlowType], Dezimal] = {}
    entry_count, missing_conversion_count = 0, 0
    wants_label_ids = wants_label_ids or set()

    for flow in flows:
        months = target_months(flow, from_date, to_date)
        if not months or flow.label_id in excluded_label_ids:
            continue
        entry_count += 1
        amount = convert(
            flow.amount * MONTHLY_MULTIPLIERS[flow.frequency] * months, flow.currency
        )
        if amount is None:
            missing_conversion_count += 1
            continue
        if flow.flow_type == FlowType.EARNING:
            expected_income += amount
        else:
            expected_expenses += amount
            if flow.label_id in wants_label_ids:
                expected_wants += amount
            if amount > 0:
                key = (flow.label_id, flow.flow_type)
                expected_by_label[key] = expected_by_label.get(key, Dezimal(0)) + amount

    expected_invested = Dezimal(0)
    for contribution in contributions or []:
        months = target_months(contribution, from_date, to_date)
        if not months:
            continue
        entry_count += 1
        amount = convert(
            contribution.amount
            * CONTRIBUTION_MONTHLY_MULTIPLIERS[contribution.frequency]
            * months,
            contribution.currency,
        )
        if amount is None:
            missing_conversion_count += 1
        else:
            expected_invested += amount

    actual_invested = Dezimal(0)
    invested_actual_complete = True
    for tx in investment_txs or []:
        direction = INVESTMENT_DIRECTIONS.get(tx.type)
        if direction is None:
            continue
        if not from_date <= tx.date.date() <= to_date:
            continue
        amount = convert(abs(tx.amount), tx.currency)
        if amount is None:
            missing_conversion_count += 1
            invested_actual_complete = False
        else:
            actual_invested += amount * direction
            track(tx.date.date(), 2, amount * direction)

    savings_label_ids = savings_label_ids or set()
    actual_savings = Dezimal(0)
    savings_actual_complete = True
    for tx in account_txs or []:
        if (
            tx.type not in (TxType.INFLOW, TxType.OUTFLOW)
            or tx.linked_tx
            or not from_date <= tx.date.date() <= to_date
            or not any(label.label_id in savings_label_ids for label in tx.labels or [])
        ):
            continue
        amount = convert(abs(tx.amount), tx.currency)
        if amount is None:
            missing_conversion_count += 1
            savings_actual_complete = False
        else:
            saved = amount if tx.type == TxType.OUTFLOW else -amount
            actual_savings += saved
            track(tx.date.date(), 2, saved)

    actual_spending = {
        "needs": actual_expenses if account_txs is None else Dezimal(0),
        "wants": Dezimal(0),
    }
    spending_complete = {"needs": True, "wants": True}
    for tx in account_txs or []:
        if (
            tx.type not in (TxType.OUTFLOW, TxType.FEE)
            or tx.linked_tx
            or not from_date <= tx.date.date() <= to_date
            or any(label.label_id in excluded_label_ids for label in tx.labels or [])
        ):
            continue
        group = (
            "wants"
            if any(label.label_id in wants_label_ids for label in tx.labels or [])
            else "needs"
        )
        amount = convert(abs(tx.amount), tx.currency)
        if amount is None:
            missing_conversion_count += 1
            spending_complete[group] = False
        else:
            actual_spending[group] += amount
            track(tx.date.date(), 0 if group == "needs" else 1, amount)

    if all(spending_complete.values()):
        actual_spending["needs"] = round(
            actual_spending["needs"] + actual_spending["wants"], 2
        ) - round(actual_spending["wants"], 2)

    invested_breakdown = BudgetInvestmentBreakdown(
        savings=round(actual_savings, 2) if savings_actual_complete else None,
        transactions=round(actual_invested, 2) if invested_actual_complete else None,
    )
    combined_invested = (
        invested_breakdown.savings + invested_breakdown.transactions
        if invested_breakdown.savings is not None
        and invested_breakdown.transactions is not None
        else None
    )

    series = []
    if period_of is not None:
        income_by_period = income_by_period or {}
        for period in sorted(set(periods) | set(income_by_period)):
            needs, wants, invested = periods.get(period, [Dezimal(0)] * 3)
            series.append(
                BudgetPoint(
                    period=period,
                    needs=round(needs, 2),
                    wants=round(wants, 2),
                    invested=round(invested, 2),
                    remainder=round(
                        income_by_period.get(period, Dezimal(0))
                        - needs
                        - wants
                        - invested,
                        2,
                    ),
                )
            )

    expected_income = round(expected_income, 2)
    expected_expenses = round(expected_expenses, 2)
    expected_wants = round(expected_wants, 2)
    expected_needs = expected_expenses - expected_wants
    complete = missing_conversion_count == 0
    by_label = []
    for label_id, flow_type in sorted(
        expected_by_label, key=lambda key: (key[1].value, str(key[0]))
    ):
        actual = (
            actual_by_label.get(label_id, (Dezimal(0), Dezimal(0)))[
                0 if flow_type == FlowType.EARNING else 1
            ]
            if label_id is not None
            else None
        )
        by_label.append(
            BudgetLabelComparison(
                label_id=label_id,
                flow_type=flow_type,
                comparison=_comparison(
                    expected_by_label[(label_id, flow_type)],
                    actual,
                    complete,
                ),
            )
        )

    return BudgetSummary(
        from_month=from_date.replace(day=1),
        to_month=to_date.replace(day=1),
        entry_count=entry_count,
        missing_conversion_count=missing_conversion_count,
        income=_comparison(expected_income, actual_income, complete),
        expenses=_comparison(expected_expenses, actual_expenses, complete),
        needs=_comparison(
            expected_needs,
            actual_spending["needs"] if spending_complete["needs"] else None,
            complete,
        ),
        wants=_comparison(
            expected_wants,
            actual_spending["wants"] if spending_complete["wants"] else None,
            complete,
        ),
        saved=_comparison(
            expected_income - expected_expenses,
            actual_saved
            if actual_saved is not None
            else actual_income - actual_expenses,
            complete,
        ),
        invested=_comparison(
            expected_invested,
            combined_invested,
            complete,
        ),
        by_label=by_label,
        invested_breakdown=invested_breakdown,
        series=series,
    )
