from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.dezimal import Dezimal
from domain.fetch_pointer import FetchPointer, FetchPointerContext
from domain.fetch_result import FetchOptions
from infrastructure.client.entity.financial.myinvestor.v2.myinvestor_fetcher import (
    DEPOSIT_TXS_POINTER,
    FUND_ORDERS_POINTER,
    MyInvestorFetcherV2,
    PENSION_ORDERS_POINTER,
    STOCK_ORDERS_POINTER,
)


@pytest.mark.asyncio
async def test_reversed_interest_preserves_negative_amount():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    fetcher._client.get_account_movements = AsyncMock(
        return_value={
            "flowList": [
                {
                    "reference": "001849",
                    "operationClass": "0",
                    "operationType": "INTERESES S/F",
                    "operationDate": "2026-08-10T00:00:00.000Z",
                    "currency": "EUR",
                    "concept": "regularizacion intereses julio",
                    "amount": "-0.1800",
                }
            ]
        }
    )

    result = await fetcher._classify_account_txs(
        account={"accountId": "account-id", "accountType": "CASH_ACCOUNT"},
        registered_txs=set(),
        related_security_account_id=None,
        min_date=date.today(),
    )

    interest_tx = result["interests"][0]

    assert interest_tx.amount == Dezimal("-0.18")
    assert interest_tx.retentions == Dezimal("-0.03")
    assert interest_tx.net_amount == Dezimal("-0.15")


def _pointer_options(pointer=None):
    entity_id = uuid4()
    entity_account_id = uuid4()
    pointers = {}
    if pointer:
        pointers[pointer.key] = pointer
    return FetchOptions(
        pointer_context=FetchPointerContext(
            entity_id=entity_id,
            entity_account_id=entity_account_id,
            pointers=pointers,
        )
    )


@pytest.mark.asyncio
async def test_account_movement_pointer_bounds_empty_history():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    fetcher._client.get_account_movements = AsyncMock(return_value={"flowList": []})
    options = _pointer_options()
    account = {"accountId": "account-id", "accountType": "CASH_ACCOUNT"}
    initial_min_date = date(2020, 1, 1)

    await fetcher._classify_account_txs(account, set(), None, initial_min_date, options)

    pointer_key = f"{DEPOSIT_TXS_POINTER}:account-id"
    assert options.pointer_context.pointers[pointer_key].threshold == date.today()
    assert fetcher._client.get_account_movements.await_count > 1

    fetcher._client.get_account_movements.reset_mock()
    await fetcher._classify_account_txs(account, set(), None, initial_min_date, options)

    assert fetcher._client.get_account_movements.await_count == 1
    request = fetcher._client.get_account_movements.await_args
    assert request.args[1] == date.today()
    assert request.args[2] == date.today()


@pytest.mark.asyncio
async def test_account_movement_pointer_uses_latest_transaction_regardless_of_type():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    latest_tx_date = date.today() - timedelta(days=3)
    older_deposit_date = date.today() - timedelta(days=10)
    fetcher._client.get_account_movements = AsyncMock(
        return_value={
            "flowList": [
                {
                    "reference": "latest-interest",
                    "operationClass": "0",
                    "operationType": "INTERESES S/F",
                    "operationDate": f"{latest_tx_date.isoformat()}T12:00:00.000Z",
                    "currency": "EUR",
                    "concept": "account interest",
                    "amount": "1.00",
                },
                {
                    "reference": "older-deposit",
                    "operationClass": "MOVIMIENTOS DEPOSITOS",
                    "operationType": "CARGO P/DEPOSITO",
                    "operationDate": f"{older_deposit_date.isoformat()}T12:00:00.000Z",
                    "currency": "EUR",
                    "concept": "term deposit",
                    "amount": "10.00",
                },
            ]
        }
    )
    options = _pointer_options()

    result = await fetcher._classify_account_txs(
        {"accountId": "account-id", "accountType": "CASH_ACCOUNT"},
        set(),
        None,
        date.today() - timedelta(days=30),
        options,
    )

    pointer_key = f"{DEPOSIT_TXS_POINTER}:account-id"
    assert options.pointer_context.pointers[pointer_key].threshold == latest_tx_date
    assert [transaction.ref for transaction in result["deposit"]] == ["older-deposit"]


@pytest.mark.asyncio
async def test_account_movement_pointer_keeps_registered_boundary_inclusive():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    boundary = date.today() - timedelta(days=5)
    fetcher._client.get_account_movements = AsyncMock(
        return_value={
            "flowList": [
                {
                    "reference": "registered-ref",
                    "operationDate": f"{boundary.isoformat()}T12:00:00.000Z",
                }
            ]
        }
    )
    options = _pointer_options()
    account = {"accountId": "account-id", "accountType": "CASH_ACCOUNT"}

    await fetcher._classify_account_txs(
        account, {"registered-ref"}, None, date(2020, 1, 1), options
    )

    pointer_key = f"{DEPOSIT_TXS_POINTER}:account-id"
    assert options.pointer_context.pointers[pointer_key].threshold == boundary

    fetcher._client.get_account_movements.reset_mock()
    await fetcher._classify_account_txs(
        account, {"registered-ref"}, None, date(2020, 1, 1), options
    )

    request = fetcher._client.get_account_movements.await_args
    assert request.args[1] == boundary
    assert request.args[2] == date.today()


@pytest.mark.asyncio
async def test_account_movement_pointer_is_unchanged_when_fetch_fails():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    fetcher._client.get_account_movements = AsyncMock(
        side_effect=RuntimeError("movement request failed")
    )
    previous_threshold = date.today() - timedelta(days=30)
    pointer = FetchPointer(
        entity_id=uuid4(),
        entity_account_id=uuid4(),
        key=f"{DEPOSIT_TXS_POINTER}:account-id",
        threshold=previous_threshold,
    )
    options = _pointer_options(pointer)

    with pytest.raises(RuntimeError, match="movement request failed"):
        await fetcher._classify_account_txs(
            {"accountId": "account-id", "accountType": "CASH_ACCOUNT"},
            set(),
            None,
            date(2020, 1, 1),
            options,
        )

    assert options.pointer_context.pointers[pointer.key].threshold == previous_threshold


def _complete_fund_order(reference, order_date="2025-01-01"):
    return {
        "reference": reference,
        "status": "COMPLETE",
        "orderDate": order_date,
        "operationType": "INVESTMENT_FUNDS_SUBSCRIPTION",
        "fundName": "Test Fund",
        "currency": "EUR",
        "isin": "IE00TEST",
        "market": "TEST",
    }


def _complete_fund_order_details():
    return {
        "orderDate": "2025-01-01T00:00:00.000Z",
        "executionDate": "2025-01-02T00:00:00.000Z",
        "executedShares": "1",
        "liquidationValue": "10",
        "grossAmountOperationFundCurrency": "10",
        "netAmountFundCurrency": "10",
        "commissions": "0",
        "relatedOperations": [],
    }


@pytest.mark.asyncio
async def test_fund_orders_fetch_all_statuses_and_bookkeep_registered_pending_order():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    fetcher._client.get_fund_orders = AsyncMock(
        return_value=[
            {
                "reference": "pending-ref",
                "status": "PENDING",
                "orderDate": "2024-01-01",
                "operationType": "INVESTMENT_FUNDS_SUBSCRIPTION",
            },
            _complete_fund_order("complete-ref"),
        ]
    )
    fetcher._client.get_fund_order_details = AsyncMock(
        return_value=_complete_fund_order_details()
    )
    options = _pointer_options()

    transactions = await fetcher.fetch_fund_txs(
        "security-account", {"pending-ref"}, date(2020, 1, 1), options
    )

    request = fetcher._client.get_fund_orders.await_args.kwargs
    assert request["status"] is None
    assert request["from_date"] == date(2020, 1, 1)
    assert [transaction.ref for transaction in transactions] == ["complete-ref"]
    fetcher._client.get_fund_order_details.assert_awaited_once_with(
        "security-account", "complete-ref"
    )
    pointer = options.pointer_context.pointers[
        f"{FUND_ORDERS_POINTER}:security-account"
    ]
    assert pointer.threshold == date(2024, 1, 1)


@pytest.mark.asyncio
async def test_pending_fund_order_is_rechecked_until_it_completes():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    fetcher._client.get_fund_orders = AsyncMock(
        return_value=[
            {
                "reference": "pending-ref",
                "status": "PENDING",
                "orderDate": "2024-01-01",
            }
        ]
    )
    fetcher._client.get_fund_order_details = AsyncMock(
        return_value=_complete_fund_order_details()
    )
    options = _pointer_options()

    await fetcher.fetch_fund_txs("security-account", set(), date(2020, 1, 1), options)
    first_pointer = options.pointer_context.pointers[
        f"{FUND_ORDERS_POINTER}:security-account"
    ]

    fetcher._client.get_fund_orders.return_value = [
        _complete_fund_order("pending-ref", order_date="2024-01-01")
    ]
    transactions = await fetcher.fetch_fund_txs(
        "security-account", set(), date(2020, 1, 1), options
    )

    second_request = fetcher._client.get_fund_orders.await_args_list[1].kwargs
    assert second_request["from_date"] == first_pointer.threshold
    assert [transaction.ref for transaction in transactions] == ["pending-ref"]
    assert (
        options.pointer_context.pointers[
            f"{FUND_ORDERS_POINTER}:security-account"
        ].threshold
        == date.today()
    )


@pytest.mark.asyncio
async def test_pension_orders_fetch_all_statuses():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    fetcher._client.get_pension_plan_orders = AsyncMock(return_value=[])
    options = _pointer_options()

    await fetcher._fetch_pension_fund_txs(
        "pension-account", set(), date(2020, 1, 1), options
    )

    request = fetcher._client.get_pension_plan_orders.await_args.kwargs
    assert request["status"] is None
    assert request["from_date"] == date(2020, 1, 1)
    assert (
        options.pointer_context.pointers[
            f"{PENSION_ORDERS_POINTER}:pension-account"
        ].threshold
        == date.today()
    )


@pytest.mark.asyncio
async def test_stock_pointer_clamps_first_window_to_inclusive_lower_bound():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    fetcher._client.get_stock_orders = AsyncMock(return_value=[])
    today = date.today()
    pointer = FetchPointer(
        entity_id=uuid4(),
        entity_account_id=uuid4(),
        key=f"{STOCK_ORDERS_POINTER}:security-account",
        threshold=today,
    )
    options = _pointer_options(pointer)

    await fetcher.fetch_stock_txs("security-account", set(), date(2020, 1, 1), options)

    request = fetcher._client.get_stock_orders.await_args.kwargs
    assert request["from_date"] == today
    assert request["to_date"] == today
    assert request["status"] is None
