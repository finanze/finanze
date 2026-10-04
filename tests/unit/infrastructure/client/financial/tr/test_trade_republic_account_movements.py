from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.dezimal import Dezimal
from domain.fetch_pointer import FetchPointer, FetchPointerContext
from domain.fetch_result import FetchOptions
from domain.transactions import TxType
from infrastructure.client.entity.financial.tr.trade_republic_fetcher import (
    ACCOUNT_TXS_POINTER,
    TradeRepublicFetcher,
)


def _options(pointer_threshold=None):
    context = FetchPointerContext(
        entity_id=uuid4(), entity_account_id=uuid4(), pointers={}
    )
    if pointer_threshold:
        context.pointers[ACCOUNT_TXS_POINTER] = FetchPointer(
            entity_id=context.entity_id,
            entity_account_id=context.entity_account_id,
            key=ACCOUNT_TXS_POINTER,
            threshold=pointer_threshold,
        )
    return FetchOptions(pointer_context=context)


def _event(event_id, event_type, value, title="Mercadona", status="EXECUTED"):
    return {
        "id": event_id,
        "title": title,
        "subtitle": None,
        "status": status,
        "eventType": event_type,
        "timestamp": "2026-09-20T10:15:00.000+0000",
        "amount": {"currency": "EUR", "value": value, "fractionDigits": 2},
    }


def _fetcher(movement_events):
    fetcher = TradeRepublicFetcher()
    fetcher._client = MagicMock()

    async def get_transactions(**kwargs):
        return movement_events if kwargs.get("with_details") is False else []

    fetcher._client.get_transactions = AsyncMock(side_effect=get_transactions)
    fetcher._client.get_user_info = AsyncMock(
        return_value={"cashAccount": {"iban": "DE00 1001 1001 0000 0000 01"}}
    )
    return fetcher


@pytest.mark.asyncio
async def test_maps_transfers_and_card_payments_as_account_movements():
    fetcher = _fetcher(
        [
            _event("card-1", "card_successful_transaction", -12.5, "  Mercadona  "),
            _event("in-1", "INCOMING_TRANSFER", 100, "Marcos Alvarez"),
            _event("pending-1", "CARD_SUCCESSFUL_TRANSACTION", -3, status="PENDING"),
            _event("known-1", "PAYMENT_OUTBOUND", -50),
            _event("order-1", "ORDER_EXECUTED", -200, "Apple"),
            _event("saveback-1", "benefits_saveback_execution", 5),
        ]
    )
    options = _options()

    result = await fetcher.transactions({"known-1"}, options)

    movements = result.account
    assert [(tx.ref, tx.type, tx.amount, tx.name) for tx in movements] == [
        ("card-1", TxType.OUTFLOW, Dezimal("12.5"), "Mercadona"),
        ("in-1", TxType.INFLOW, Dezimal("100"), "Marcos Alvarez"),
    ]
    assert movements[0].date.tzinfo is not None
    assert {tx.iban for tx in movements} == {"DE00100110010000000001"}
    assert options.pointer_context.pointers[ACCOUNT_TXS_POINTER].threshold == (
        date.today()
    )
    movement_call = fetcher._client.get_transactions.await_args_list[-1]
    assert movement_call.kwargs["since"] == datetime.combine(
        date.today() - timedelta(days=730), time.min
    )


@pytest.mark.asyncio
async def test_rescans_settle_window_from_pointer():
    fetcher = _fetcher([])
    threshold = date.today() - timedelta(days=3)

    await fetcher.transactions(set(), _options(pointer_threshold=threshold))

    movement_call = fetcher._client.get_transactions.await_args_list[-1]
    assert movement_call.kwargs["since"] == datetime.combine(
        threshold - timedelta(days=10), time.min
    )


@pytest.mark.asyncio
async def test_movement_errors_keep_other_transactions_and_pointer():
    fetcher = TradeRepublicFetcher()
    fetcher._client = MagicMock()

    async def get_transactions(**kwargs):
        if kwargs.get("with_details") is False:
            raise RuntimeError("timeline down")
        return []

    fetcher._client.get_transactions = AsyncMock(side_effect=get_transactions)
    options = _options()

    result = await fetcher.transactions(set(), options)

    assert result.account == []
    assert ACCOUNT_TXS_POINTER not in options.pointer_context.pointers
