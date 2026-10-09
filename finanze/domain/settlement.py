from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.transactions import (
    AccountTx,
    AccountTxSelection,
    BaseInvestmentTx,
    TxType,
)

SETTLEMENT_MAX_DAYS = 5
SETTLEMENT_AMOUNT_TOLERANCE = Dezimal("0.01")

SETTLEMENT_TYPES_BY_DIRECTION = {
    TxType.OUTFLOW: {
        TxType.BUY,
        TxType.SUBSCRIPTION,
        TxType.INVESTMENT,
        TxType.RIGHT_ISSUE,
    },
    TxType.INFLOW: {
        TxType.SELL,
        TxType.REPAYMENT,
        TxType.DIVIDEND,
        TxType.INTEREST,
        TxType.RIGHT_SELL,
    },
}


def settlement_window(investment_txs: list[BaseInvestmentTx]) -> AccountTxSelection:
    gap = timedelta(days=SETTLEMENT_MAX_DAYS)
    return AccountTxSelection(
        entities=list({tx.entity.id for tx in investment_txs}),
        from_date=min(tx.date.date() for tx in investment_txs) - gap,
        to_date=max(tx.date.date() for tx in investment_txs) + gap,
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=tzlocal())


def _amount_distance(
    account_tx: AccountTx, investment_tx: BaseInvestmentTx
) -> Optional[Dezimal]:
    target = abs(account_tx.amount)
    distances = []
    for candidate in (investment_tx.amount, getattr(investment_tx, "net_amount", None)):
        if candidate is None:
            continue
        distance = abs(target - abs(candidate))
        if distance <= SETTLEMENT_AMOUNT_TOLERANCE:
            distances.append(distance)
    return min(distances) if distances else None


def match_settlements(
    account_txs: list[AccountTx],
    investment_txs: list[BaseInvestmentTx],
    taken_refs: set[tuple[UUID, str]],
) -> dict[UUID, str]:
    max_gap = timedelta(days=SETTLEMENT_MAX_DAYS)
    candidates = []
    for account_tx in account_txs:
        if account_tx.linked_tx or account_tx.labels_locked:
            continue
        allowed_types = SETTLEMENT_TYPES_BY_DIRECTION.get(account_tx.type)
        if not allowed_types:
            continue
        for investment_tx in investment_txs:
            if investment_tx.type not in allowed_types:
                continue
            if investment_tx.entity.id != account_tx.entity.id:
                continue
            if investment_tx.currency.upper() != account_tx.currency.upper():
                continue
            if (account_tx.entity.id, investment_tx.ref) in taken_refs:
                continue
            gap = abs(_aware(account_tx.date) - _aware(investment_tx.date))
            if gap > max_gap:
                continue
            distance = _amount_distance(account_tx, investment_tx)
            if distance is None:
                continue
            candidates.append((gap, distance, account_tx, investment_tx))

    candidates.sort(key=lambda c: (c[0], c[1].val))

    links: dict[UUID, str] = {}
    used_investment_refs: set[tuple[UUID, str]] = set()
    for _, _, account_tx, investment_tx in candidates:
        investment_key = (investment_tx.entity.id, investment_tx.ref)
        if account_tx.id in links or investment_key in used_investment_refs:
            continue
        links[account_tx.id] = investment_tx.ref
        used_investment_refs.add(investment_key)

    return links
