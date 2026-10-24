from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.dezimal import Dezimal
from domain.fetch_pointer import FetchPointer, FetchPointerContext
from domain.fetch_result import FetchOptions
from domain.transactions import TxType
from infrastructure.client.entity.financial.myinvestor.v2.myinvestor_fetcher import (
    ACCOUNT_TXS_POINTER,
    DEPOSIT_TXS_POINTER,
    DIVIDENDS_POINTER,
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


def _movement(reference, tx_date, amount, operation_class="TRANSFERENCIAS", **extra):
    return {
        "reference": reference,
        "operationClass": operation_class,
        "operationType": extra.pop("operation_type", "TRANSFERENCIA"),
        "operationDate": f"{tx_date.isoformat()}T12:00:00.000Z",
        "currency": "EUR",
        "concept": extra.pop("concept", f"Concept {reference}"),
        "amount": amount,
        **extra,
    }


@pytest.mark.asyncio
async def test_generic_cash_account_movements_are_mapped_by_sign():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    recent = date.today() - timedelta(days=2)
    fetcher._client.get_account_movements = AsyncMock(
        return_value={
            "flowList": [
                _movement("in-1", recent, "1500.00", concept=" Nomina "),
                _movement("out-1", recent, "-45.20", concept="Supermercado"),
                _movement("zero-1", recent, "0"),
                _movement(
                    "int-1",
                    recent,
                    "1.00",
                    operation_class="0",
                    operation_type="INTERESES S/F",
                ),
                _movement(
                    "ret-1",
                    recent,
                    "-0.19",
                    operation_class="ME",
                    operation_type="RETE.LIQUIDA",
                ),
            ]
        }
    )
    options = _pointer_options()

    result = await fetcher._classify_account_txs(
        {
            "accountId": "account-id",
            "accountType": "CASH_ACCOUNT",
            "iban": "ES12 1544 0000 0000 0000 0001",
        },
        set(),
        None,
        date.today() - timedelta(days=10),
        options,
    )

    movements = {tx.ref: tx for tx in result["movements"]}
    assert set(movements) == {"in-1", "out-1"}
    assert {tx.iban for tx in result["movements"] + result["interests"]} == {
        "ES1215440000000000000001"
    }
    assert movements["in-1"].type == TxType.INFLOW
    assert movements["in-1"].amount == Dezimal("1500.00")
    assert movements["in-1"].name == "Nomina"
    assert movements["out-1"].type == TxType.OUTFLOW
    assert movements["out-1"].amount == Dezimal("45.20")
    assert [tx.ref for tx in result["interests"]] == ["int-1"]
    assert (
        options.pointer_context.pointers[f"{ACCOUNT_TXS_POINTER}:account-id"].threshold
        == recent
    )


@pytest.mark.asyncio
async def test_generic_movements_skip_registered_refs_without_stopping():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    recent = date.today() - timedelta(days=1)
    fetcher._client.get_account_movements = AsyncMock(
        return_value={
            "flowList": [
                _movement("known", recent, "-10"),
                _movement("new", recent, "-20"),
            ]
        }
    )

    result = await fetcher._classify_account_txs(
        {"accountId": "account-id", "accountType": "CASH_ACCOUNT"},
        {"known"},
        None,
        date.today() - timedelta(days=5),
        _pointer_options(),
    )

    assert [tx.ref for tx in result["movements"]] == ["new"]


@pytest.mark.asyncio
async def test_generic_movements_lookback_is_capped_to_two_years():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    old = date.today() - timedelta(days=3 * 365)
    fetcher._client.get_account_movements = AsyncMock(
        return_value={"flowList": [_movement("old", old, "-10")]}
    )
    deposit_pointer = FetchPointer(
        entity_id=uuid4(),
        entity_account_id=uuid4(),
        key=f"{DEPOSIT_TXS_POINTER}:account-id",
        threshold=date.today(),
    )

    result = await fetcher._classify_account_txs(
        {"accountId": "account-id", "accountType": "CASH_ACCOUNT"},
        set(),
        None,
        date(2018, 1, 1),
        _pointer_options(deposit_pointer),
    )

    first_from = min(
        call.args[1] for call in fetcher._client.get_account_movements.await_args_list
    )
    assert first_from >= date.today() - timedelta(days=2 * 366)
    assert result["movements"] == []


@pytest.mark.asyncio
async def test_portfolio_account_does_not_emit_generic_movements():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    fetcher._client.get_security_account_details = AsyncMock(return_value={})
    recent = date.today() - timedelta(days=1)
    fetcher._client.get_account_movements = AsyncMock(
        return_value={"flowList": [_movement("transfer", recent, "100")]}
    )

    result = await fetcher._classify_account_txs(
        {"accountId": "account-id", "accountType": "CASH_PORTFOLIO"},
        set(),
        "security-id",
        date.today() - timedelta(days=5),
        _pointer_options(),
    )

    assert result["movements"] == []


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


def _dividend_flow(tx_date=None, **changes):
    flow = _movement(
        "dividend-cash",
        tx_date or date.today(),
        "0.08",
        operation_class="RENDIMIENTOS DE VALORES",
        operation_type="ABONO DE DIVIDENDO",
        concept="JPM GB EQ PR IN ACT UT E-U D @",
        operationRef="0000 JPM GB EQ PR IN ACT UT E-U D @ 1        000000001",
    )
    return {**flow, **changes}


def _dividend_event(tx_date=None, **changes):
    return {
        "eventId": "paid-event",
        "eventType": "DE",
        "eventStatus": "VALIDATED",
        "isin": "IE000AP27VA7",
        "ticker": "JGPD GR",
        "marketId": "XTR",
        "toolDescription": "JPM GB EQ PR IN ACT UT E-U D",
        "operationDate": f"{(tx_date or date.today()).isoformat()}T00:00:00Z",
        **changes,
    }


def _dividend_details(tx_date=None, **changes):
    return {
        "eventType": "DE",
        "originEmissionIsin": "IE000AP27VA7",
        "originEmissionCurrency": "EUR",
        "eventCurrency": "EUR",
        "ticker": "JGPD GR",
        "toolDescription": "JPM GB EQ PR IN ACT UT E-U D",
        "execDate": f"{(tx_date or date.today()).isoformat()}T00:00:00Z",
        "taxSharesMarketExpenses": "0.0992",
        "taxSharesOriginWithholding": "0",
        "taxSharesDestinationWithholding": "0.018848",
        "marketExpensesPercent": "0",
        **changes,
    }


def _dividend_fetcher(flows=None, events=None, details=None):
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    fetcher._client.get_account_movements = AsyncMock(
        return_value={"flowList": flows if flows is not None else [_dividend_flow()]}
    )
    fetcher._client.get_financial_events = AsyncMock(
        return_value=events if events is not None else [_dividend_event()]
    )
    fetcher._client.get_financial_event_details = AsyncMock(
        return_value=details if details is not None else _dividend_details()
    )
    return fetcher


async def _classify_dividends(fetcher, registered=None, options=None, min_date=None):
    return await fetcher._classify_account_txs(
        {"accountId": "cash-account", "accountType": "CASH_ACCOUNT"},
        registered or set(),
        "security-account",
        min_date or date.today() - timedelta(days=30),
        options or _pointer_options(),
    )


@pytest.mark.asyncio
async def test_dividends_require_paid_cash_and_reconcile_per_share_tax():
    fetcher = _dividend_fetcher(
        events=[
            _dividend_event(),
            _dividend_event(date.today() - timedelta(days=16), eventId="unpaid-event"),
        ]
    )
    options = _pointer_options()

    result = await _classify_dividends(fetcher, options=options)

    dividend = result["dividends"][0]
    assert dividend.type == TxType.DIVIDEND
    assert dividend.amount == Dezimal("0.10")
    assert dividend.retentions == Dezimal("0.02")
    assert dividend.net_amount == Dezimal("0.08")
    assert dividend.shares == Dezimal(1)
    assert dividend.price == dividend.fees == Dezimal(0)
    assert dividend.isin == "IE000AP27VA7"
    assert dividend.ticker == "JGPD GR"
    assert dividend.market == "XTR"
    assert dividend.date.tzinfo is not None
    assert dividend.linked_tx == "dividend-cash"
    assert result["movements"][0].linked_tx == dividend.ref
    assert dividend.ref == "dividend:security-account:dividend-cash"
    fetcher._client.get_account_movements.assert_awaited_once()
    fetcher._client.get_financial_events.assert_awaited_once_with("security-account")
    fetcher._client.get_financial_event_details.assert_awaited_once_with(
        "security-account", "paid-event"
    )
    assert (
        options.pointer_context.pointers[
            f"{DIVIDENDS_POINTER}:security-account"
        ].threshold
        == date.today()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "registered", [set(), {"dividend:security-account:dividend-cash"}]
)
async def test_no_unresolved_dividend_flows_skip_event_requests(registered):
    fetcher = _dividend_fetcher(flows=[] if not registered else None)

    result = await _classify_dividends(fetcher, registered)

    assert result["dividends"] == []
    fetcher._client.get_financial_events.assert_not_awaited()
    fetcher._client.get_financial_event_details.assert_not_awaited()


@pytest.mark.asyncio
async def test_registered_cash_still_produces_dividend_without_duplicate_movement():
    result = await _classify_dividends(_dividend_fetcher(), {"dividend-cash"})

    assert result["movements"] == []
    assert len(result["dividends"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flow_changes,detail_changes",
    [
        ({"amount": "0.09"}, {}),
        ({"operationRef": ""}, {}),
        ({"operationRef": "asset @ 1,5 0000"}, {}),
        ({"operationRef": "asset @ 1 @ 2 0000"}, {}),
        ({"operationRef": "asset @ 0 0000"}, {}),
        ({}, {"marketExpensesPercent": "1"}),
        ({}, {"eventCurrency": "USD"}),
        ({}, {"originEmissionIsin": "wrong-isin"}),
        ({}, {"taxSharesMarketExpenses": "NaN"}),
        ({}, {"taxSharesDestinationWithholding": "-0.01"}),
    ],
)
async def test_unreconciled_dividend_remains_generic_and_retryable(
    flow_changes, detail_changes
):
    paid_date = date.today() - timedelta(days=2)
    fetcher = _dividend_fetcher(
        flows=[_dividend_flow(paid_date, **flow_changes)],
        details=_dividend_details(**detail_changes),
    )
    options = _pointer_options()

    result = await _classify_dividends(fetcher, options=options)

    assert result["dividends"] == []
    assert result["movements"][0].linked_tx is None
    assert (
        options.pointer_context.pointers[
            f"{DIVIDENDS_POINTER}:security-account"
        ].threshold
        == paid_date
    )


@pytest.mark.asyncio
async def test_ambiguous_dividend_events_do_not_guess():
    fetcher = _dividend_fetcher(
        events=[_dividend_event(), _dividend_event(eventId="other-event")]
    )

    result = await _classify_dividends(fetcher)

    assert result["dividends"] == []
    assert result["movements"][0].linked_tx is None


@pytest.mark.asyncio
async def test_dividend_event_cannot_be_reused_for_two_cash_credits():
    fetcher = _dividend_fetcher(
        flows=[_dividend_flow(), _dividend_flow(reference="other-cash")]
    )

    result = await _classify_dividends(fetcher)

    assert result["dividends"] == []
    fetcher._client.get_financial_event_details.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failed_method", ["get_financial_events", "get_financial_event_details"]
)
async def test_event_failure_preserves_cash_and_dividend_retry(failed_method):
    fetcher = _dividend_fetcher()
    getattr(fetcher._client, failed_method).side_effect = RuntimeError("unavailable")
    options = _pointer_options()

    result = await _classify_dividends(fetcher, options=options)

    assert result["dividends"] == []
    assert len(result["movements"]) == 1
    assert (
        options.pointer_context.pointers[
            f"{DIVIDENDS_POINTER}:security-account"
        ].threshold
        == date.today()
    )


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


@pytest.mark.asyncio
@pytest.mark.parametrize("deep", [False, True])
async def test_historical_dividends_require_deep_refresh_for_existing_connection(deep):
    paid_date = date.today() - timedelta(days=60)
    fetcher = _dividend_fetcher(
        flows=[_dividend_flow(paid_date)],
        events=[_dividend_event(paid_date)],
        details=_dividend_details(paid_date),
    )
    options = _pointer_options(
        FetchPointer(
            entity_id=uuid4(),
            entity_account_id=uuid4(),
            key=f"{ACCOUNT_TXS_POINTER}:cash-account",
            threshold=date.today(),
        )
        if not deep
        else None
    )
    options.deep = deep

    result = await _classify_dividends(
        fetcher,
        registered=set() if deep else {"dividend-cash"},
        options=options,
        min_date=paid_date,
    )

    assert len(result["dividends"]) == (1 if deep else 0)
    assert fetcher._client.get_financial_events.await_count == (1 if deep else 0)


@pytest.mark.asyncio
async def test_delayed_event_enriches_registered_cash_on_next_sync():
    paid_date = date.today() - timedelta(days=20)
    fetcher = _dividend_fetcher(flows=[_dividend_flow(paid_date)], events=[])
    options = _pointer_options()

    first = await _classify_dividends(fetcher, options=options)

    assert first["dividends"] == []
    assert (
        options.pointer_context.pointers[
            f"{DIVIDENDS_POINTER}:security-account"
        ].threshold
        == paid_date
    )
    fetcher._client.get_financial_events.return_value = [_dividend_event(paid_date)]
    fetcher._client.get_financial_event_details.return_value = _dividend_details(
        paid_date
    )
    fetcher._client.get_account_movements.reset_mock()

    second = await _classify_dividends(fetcher, {"dividend-cash"}, options=options)

    assert len(second["dividends"]) == 1
    assert second["movements"] == []
    request = fetcher._client.get_account_movements.await_args
    assert request.args[1] == paid_date - timedelta(days=5)
    assert (
        options.pointer_context.pointers[
            f"{DIVIDENDS_POINTER}:security-account"
        ].threshold
        == date.today()
    )


@pytest.mark.asyncio
async def test_dividend_pointer_overlap_includes_boundary_and_deduplicates_next_sync():
    paid_date = date.today() - timedelta(days=5)
    fetcher = _dividend_fetcher(
        flows=[_dividend_flow(paid_date)],
        events=[_dividend_event(paid_date)],
        details=_dividend_details(paid_date),
    )
    options = _pointer_options(
        FetchPointer(
            entity_id=uuid4(),
            entity_account_id=uuid4(),
            key=f"{DIVIDENDS_POINTER}:security-account",
            threshold=date.today(),
        )
    )

    first = await _classify_dividends(fetcher, options=options)
    fetcher._client.get_financial_events.reset_mock()
    second = await _classify_dividends(
        fetcher,
        {"dividend-cash", first["dividends"][0].ref},
        options=options,
    )

    assert second["dividends"] == second["movements"] == []
    fetcher._client.get_financial_events.assert_not_awaited()


@pytest.mark.asyncio
async def test_dividend_scan_uses_one_v3_request_when_account_uuid_exists():
    fetcher = _dividend_fetcher()

    result = await fetcher._classify_account_txs(
        {
            "accountId": "cash-account",
            "accountUuid": "cash-uuid",
            "accountType": "CASH_ACCOUNT",
        },
        set(),
        "security-account",
        date.today(),
        _pointer_options(),
    )

    assert len(result["dividends"]) == 1
    fetcher._client.get_account_movements.assert_awaited_once_with(
        "cash-uuid", date.today(), date.today(), version=3
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", ["0", "-0.08"])
async def test_nonpositive_dividend_flows_never_create_dividend(amount):
    fetcher = _dividend_fetcher(flows=[_dividend_flow(amount=amount)])

    result = await _classify_dividends(fetcher)

    assert result["dividends"] == []
    fetcher._client.get_financial_events.assert_not_awaited()


@pytest.mark.asyncio
async def test_dividend_request_failure_keeps_earliest_unresolved_payment():
    paid_date = date.today() - timedelta(days=10)
    fetcher = _dividend_fetcher(flows=[_dividend_flow(paid_date)])
    fetcher._client.get_financial_events.side_effect = RuntimeError("unavailable")
    options = _pointer_options()

    result = await _classify_dividends(fetcher, options=options)

    assert len(result["movements"]) == 1
    assert (
        options.pointer_context.pointers[
            f"{DIVIDENDS_POINTER}:security-account"
        ].threshold
        == paid_date
    )


@pytest.mark.asyncio
async def test_dividend_flow_request_failure_does_not_change_pointers():
    pointer = FetchPointer(
        entity_id=uuid4(),
        entity_account_id=uuid4(),
        key=f"{DIVIDENDS_POINTER}:security-account",
        threshold=date.today() - timedelta(days=20),
    )
    options = _pointer_options(pointer)
    fetcher = _dividend_fetcher()
    fetcher._client.get_account_movements.side_effect = RuntimeError("unavailable")

    with pytest.raises(RuntimeError, match="unavailable"):
        await _classify_dividends(fetcher, options=options)

    assert options.pointer_context.pointers == {pointer.key: pointer}


@pytest.mark.asyncio
async def test_dividend_orchestration_includes_investment_and_linked_cash_leg():
    fetcher = _dividend_fetcher()
    fetcher._get_active_owned_accounts = AsyncMock(
        return_value=[
            {
                "accountId": "cash-account",
                "accountType": "CASH_ACCOUNT",
                "creationDate": date.today().isoformat(),
            }
        ]
    )
    fetcher._get_related_security_account = AsyncMock(
        return_value={"accountId": "security-account"}
    )
    fetcher._get_investment_txs = AsyncMock(return_value=[])
    fetcher._client.get_pension_accounts = AsyncMock(return_value=[])

    transactions = await fetcher.transactions(set(), _pointer_options())

    assert len(transactions.investment) == len(transactions.account) == 1
    assert transactions.account[0].linked_tx == transactions.investment[0].ref


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {}, [None]])
async def test_malformed_event_list_preserves_cash_and_retry(payload):
    fetcher = _dividend_fetcher()
    fetcher._client.get_financial_events.return_value = payload
    options = _pointer_options()

    result = await _classify_dividends(fetcher, options=options)

    assert result["dividends"] == []
    assert len(result["movements"]) == 1
    assert (
        options.pointer_context.pointers[
            f"{DIVIDENDS_POINTER}:security-account"
        ].threshold
        == date.today()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, []])
async def test_malformed_event_details_preserve_cash(payload):
    fetcher = _dividend_fetcher()
    fetcher._client.get_financial_event_details.return_value = payload

    result = await _classify_dividends(fetcher)

    assert result["dividends"] == []
    assert len(result["movements"]) == 1


@pytest.mark.asyncio
async def test_future_event_does_not_explain_an_earlier_cash_payment():
    fetcher = _dividend_fetcher(
        events=[_dividend_event(date.today() + timedelta(days=1))]
    )

    result = await _classify_dividends(fetcher)

    assert result["dividends"] == []
    fetcher._client.get_financial_event_details.assert_not_awaited()


@pytest.mark.asyncio
async def test_fractional_dividend_quantity_is_multiplied_before_rounding():
    fetcher = _dividend_fetcher(
        flows=[_dividend_flow(amount="0.12", operationRef="ETF @ 1.5 00000001")]
    )

    result = await _classify_dividends(fetcher)

    dividend = result["dividends"][0]
    assert dividend.shares == Dezimal("1.5")
    assert dividend.amount == Dezimal("0.15")
    assert dividend.retentions == Dezimal("0.03")
    assert dividend.net_amount == Dezimal("0.12")
