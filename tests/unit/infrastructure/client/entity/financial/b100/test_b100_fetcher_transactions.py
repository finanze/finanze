from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.fetch_pointer import FetchPointer, FetchPointerContext
from domain.fetch_result import FetchOptions
from domain.native_entities import B100
from domain.transactions import TxType
from infrastructure.client.entity.financial.b100.b100_fetcher import (
    ACCOUNT_MOVEMENTS_SETTLE_DAYS,
    ACCOUNT_TXS_POINTER,
    B100Fetcher,
)

IBAN = "ES7601000000000000000001"
POINTER_KEY = f"{ACCOUNT_TXS_POINTER}:{IBAN}"


def _options(pointer_threshold=None):
    context = FetchPointerContext(
        entity_id=uuid4(), entity_account_id=uuid4(), pointers={}
    )
    if pointer_threshold:
        context.pointers[POINTER_KEY] = FetchPointer(
            entity_id=context.entity_id,
            entity_account_id=context.entity_account_id,
            key=POINTER_KEY,
            threshold=pointer_threshold,
        )
    return FetchOptions(pointer_context=context)


def _timestamp(day: date) -> str:
    moment = datetime.combine(day, time(10, 30), tzinfo=tzlocal())
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.479812000Z")


def _movement(
    movement_id,
    day,
    quantity,
    detail,
    movement_type="EXPENSE",
    subtype="TransferMovement",
):
    return {
        "id": movement_id,
        "detail": detail,
        "movementType": movement_type,
        "movementSubtype": subtype,
        "amount": {"quantity": quantity, "currency": "EUR"},
        "balanceAfterTransaction": {"quantity": 1000.0, "currency": "EUR"},
        "transactionDate": _timestamp(day),
        "valueDate": _timestamp(day),
        "category": "1",
    }


def _page(movements, next_cursor=None):
    return {
        "data": movements,
        "pagination": {"next": next_cursor},
        "maxMovementsInFile": 1000,
    }


def _fetcher(pages):
    fetcher = B100Fetcher()
    fetcher._client = MagicMock()
    fetcher._client.get_accounts = AsyncMock(
        return_value=[{"id": "acc-hash", "iban": IBAN, "accountType": "CHECKING"}]
    )
    fetcher._client.get_account_movements = AsyncMock(side_effect=pages)
    return fetcher


@pytest.mark.asyncio
async def test_maps_income_expense_and_interest_movements_across_pages():
    today = date.today()
    fetcher = _fetcher(
        [
            _page(
                [
                    _movement("m1", today, 25.5, "  Bizum   to Ana ", "EXPENSE"),
                    _movement("m2", today, 1200.0, "NOMINA ACME", "INCOME"),
                ],
                next_cursor="cursor-2",
            ),
            _page(
                [
                    _movement(
                        "m3",
                        today - timedelta(days=3),
                        8.1,
                        "INTERESES CUENTA",
                        "INCOME",
                        "BaseMovement",
                    ),
                    _movement("m4", today, 5, "Unknown", "OTHER"),
                ]
            ),
        ]
    )

    result = await fetcher.transactions(set(), _options())

    txs = {tx.name: tx for tx in result.account}
    assert set(txs) == {"Bizum to Ana", "NOMINA ACME", "INTERESES CUENTA"}
    assert {tx.iban for tx in result.account} == {IBAN}

    outflow = txs["Bizum to Ana"]
    assert outflow.ref == "m1"
    assert outflow.type == TxType.OUTFLOW
    assert outflow.amount == Dezimal("25.5")
    assert outflow.net_amount == Dezimal("25.5")
    assert outflow.entity == B100
    assert outflow.date.tzinfo is not None

    assert txs["NOMINA ACME"].type == TxType.INFLOW

    interest = txs["INTERESES CUENTA"]
    assert interest.type == TxType.INTEREST
    assert interest.ref != "m3"
    assert interest.net_amount == Dezimal("8.1")
    assert interest.amount == Dezimal("10")

    calls = fetcher._client.get_account_movements.await_args_list
    assert [call.kwargs["cursor"] for call in calls] == [None, "cursor-2"]


@pytest.mark.asyncio
async def test_first_fetch_skips_registered_and_sets_pointer():
    today = date.today()
    interest = _movement(
        "m-int", today - timedelta(days=40), 4, "INTERESES", "INCOME", "BaseMovement"
    )
    registered_interest_ref = B100Fetcher()._map_interest_tx(interest).ref
    fetcher = _fetcher(
        [
            _page(
                [
                    _movement("new", today, 10, "Coffee"),
                    interest,
                    _movement("older", today - timedelta(days=60), 20, "Rent"),
                    _movement("ancient", today - timedelta(days=800), 30, "Old"),
                ],
                next_cursor="more",
            ),
        ]
    )
    options = _options()

    result = await fetcher.transactions({registered_interest_ref}, options)

    assert [tx.ref for tx in result.account] == ["new", "older"]
    assert fetcher._client.get_account_movements.await_count == 1
    assert options.pointer_context.pointers[POINTER_KEY].threshold == today


@pytest.mark.asyncio
async def test_pointer_limits_rescan_to_settle_window():
    today = date.today()
    threshold = today - timedelta(days=5)
    window_start = threshold - timedelta(days=ACCOUNT_MOVEMENTS_SETTLE_DAYS)
    fetcher = _fetcher(
        [
            _page(
                [
                    _movement("recent", today, 10, "Coffee"),
                    _movement("known", threshold, 15, "Gym"),
                    _movement("late", window_start, 12, "Late booking"),
                    _movement("stale", window_start - timedelta(days=1), 9, "X"),
                ],
                next_cursor="more",
            ),
        ]
    )
    options = _options(pointer_threshold=threshold)

    result = await fetcher.transactions({"known"}, options)

    assert [tx.ref for tx in result.account] == ["recent", "late"]
    assert fetcher._client.get_account_movements.await_count == 1
    assert options.pointer_context.pointers[POINTER_KEY].threshold == today
