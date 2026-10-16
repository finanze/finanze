import json
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.entity_login import LoginConfirmationType, LoginResultCode, TwoFactor
from domain.fetch_pointer import FetchPointer, FetchPointerContext
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions, FetchStage
from domain.global_position import ProductType
from domain.native_entities import ING
from domain.transactions import ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS, TxType
from infrastructure.client.entity.financial.ing import ing_fetcher as ing_module
from infrastructure.client.entity.financial.ing.ing_client import INGAPIClient
from infrastructure.client.entity.financial.ing.ing_fetcher import (
    INGFetcher,
    _map_movement_to_account_tx,
    _map_movement_to_stock_tx,
    _map_op_type,
)


def test_map_op_type_covers_stock_operations():
    assert _map_op_type("C", "A") == TxType.BUY
    assert _map_op_type("V", "A") == TxType.SELL
    assert _map_op_type("V", "D") == TxType.RIGHT_SELL
    assert _map_op_type("DV", "A") == TxType.DIVIDEND
    assert _map_op_type("GD", "D") == TxType.RIGHT_ISSUE
    assert _map_op_type("AC", "A") == TxType.SWAP_TO
    assert _map_op_type("BC", "A") == TxType.SWAP_FROM
    assert _map_op_type("TE", "A") == TxType.TRANSFER_IN
    assert _map_op_type("TS", "A") == TxType.TRANSFER_OUT
    assert _map_op_type("UNKNOWN", "A") is None


def test_map_movement_maps_transfer_in():
    tx = _map_movement_to_stock_tx(
        {
            "uuid": "te-ref",
            "stockType": "A",
            "stockDescription": "MAPFRE",
            "operationType": "TE",
            "stockName": "ES0124244E34",
            "stockShortName": "MAP",
            "titlesNumber": 650,
            "operationChange": 0.00,
            "operationAmount": 0.00,
            "amount": 0.00,
            "currency": "EUR",
            "effectiveDate": "28/12/2018",
            "description": "TRASP. ENTRADA",
        }
    )

    assert tx is not None
    assert tx.ref == "te-ref"
    assert tx.type == TxType.TRANSFER_IN
    assert tx.isin == "ES0124244E34"
    assert tx.shares == Dezimal("650")
    assert tx.amount == Dezimal("0")
    assert tx.net_amount == Dezimal("0")
    assert tx.fees == Dezimal("0")


@pytest.mark.parametrize(
    "amount,expected_type",
    [("1347.62", TxType.INFLOW), ("-1347.62", TxType.OUTFLOW)],
)
def test_map_account_movement_uses_signed_amount_and_stable_reference(
    amount, expected_type
):
    movement = {
        "transactionId": {"productId": "account-uuid", "transactionSequence": 2438},
        "amount": json.loads(amount),
        "transactionDate": "2026-03-21",
        "description": "Transferencia de prueba",
        "concept": "Movimiento ING",
        "transactionLocalUUID": "opaque-local-id",
        "mode": "P",
    }

    tx = _map_movement_to_account_tx(movement, "EUR", "es12 3456 7890")

    assert tx.ref == "account-uuid:2438"
    assert tx.name == "Transferencia de prueba"
    assert tx.type == expected_type
    assert tx.amount == Dezimal("1347.62")
    assert tx.net_amount == tx.amount
    assert tx.currency == "EUR"
    assert tx.iban == "ES1234567890"
    assert tx.date.isoformat().startswith("2026-03-21T00:00:00")
    assert tx.date.utcoffset() is not None
    assert tx.source == DataSource.REAL
    assert tx.product_type == ProductType.ACCOUNT
    assert tx.fees == tx.retentions == Dezimal(0)

    movement["transactionLocalUUID"] = "different-session-local-id"
    assert _map_movement_to_account_tx(movement, "EUR").ref == tx.ref
    movement["transactionId"]["productId"] = "other-account-uuid"
    assert _map_movement_to_account_tx(movement, "EUR").ref != tx.ref


@pytest.mark.parametrize(
    "overrides",
    [
        {"transactionId": {}},
        {"transactionId": {"productId": "account-uuid"}},
        {"amount": None},
        {"amount": "0"},
    ],
)
def test_map_account_movement_skips_missing_reference_or_amount(overrides):
    movement = {
        "transactionId": {"productId": "account-uuid", "transactionSequence": 1},
        "amount": "10.25",
        "transactionDate": "2026-03-21",
        **overrides,
    }

    assert _map_movement_to_account_tx(movement, "EUR") is None


def test_map_account_movement_falls_back_to_concept_and_accepts_zero_sequence():
    tx = _map_movement_to_account_tx(
        {
            "transactionId": {"productId": "account-uuid", "transactionSequence": 0},
            "amount": "10.25",
            "transactionDate": "2026-03-21",
            "concept": "INSTANT TRANSFER",
        },
        "USD",
    )

    assert tx.name == "INSTANT TRANSFER"
    assert tx.ref == "account-uuid:0"
    assert tx.currency == "USD"
    assert tx.iban is None


def _account_product(
    product_id="account-uuid", product_type="CURRENT_ACCOUNT", **kwargs
):
    return {
        "uuid": product_id,
        "type": product_type,
        "denominationCurrency": "EUR",
        "identifiers": [
            {"type": "PRODUCT_NUMBER", "value": f"number-{product_id}"},
            {"type": "IBAN", "value": "es12 3456 7890"},
        ],
        **kwargs,
    }


def _account_movement(sequence, **kwargs):
    return {
        "transactionId": {"productId": "account-uuid", "transactionSequence": sequence},
        "amount": "10.25",
        "transactionDate": "2026-10-03",
        "description": "Transferencia de prueba",
        **kwargs,
    }


def _account_page(movements, **kwargs):
    return {
        "transactions": movements,
        "count": len(movements),
        "total": len(movements),
        "mayHasMoreElements": False,
        **kwargs,
    }


def _pointer_options(threshold=None, deep=False):
    context = FetchPointerContext(entity_id=ING.id, entity_account_id=uuid4())
    if threshold:
        key = "account_txs:ES1234567890"
        context.pointers[key] = FetchPointer(
            entity_id=ING.id,
            entity_account_id=context.entity_account_id,
            key=key,
            threshold=threshold,
        )
    return FetchOptions(deep=deep, pointer_context=context)


@pytest.fixture
def account_fetcher(monkeypatch):
    clock = MagicMock(wraps=datetime)
    clock.now.return_value = datetime(2026, 10, 4, tzinfo=tzlocal())
    monkeypatch.setattr(ing_module, "datetime", clock)
    fetcher = INGFetcher()
    fetcher._client = AsyncMock(spec=INGAPIClient)
    return fetcher


@pytest.mark.asyncio
async def test_transactions_fetch_account_uuid_and_preserve_investments(
    account_fetcher,
):
    fetcher = account_fetcher
    fetcher._client.get_position.return_value = {
        "products": [
            {
                "uuid": "account-uuid",
                "type": "CURRENT_ACCOUNT",
                "denominationCurrency": "EUR",
                "identifiers": [
                    {"type": "LOCAL_UUID", "value": "different-local-uuid"},
                    {"type": "IBAN", "value": "es12 3456 7890"},
                ],
            }
        ],
    }
    fetcher._client.get_account_transactions.return_value = {
        "transactions": [
            {
                "transactionId": {
                    "productId": "account-uuid",
                    "transactionSequence": 2438,
                },
                "amount": "-1347.62",
                "transactionDate": "2026-10-03",
                "description": "Transferencia de prueba",
            }
        ],
        "count": 1,
        "total": 1,
        "mayHasMoreElements": False,
    }
    stock = _map_movement_to_stock_tx(
        {
            "uuid": "stock-ref",
            "operationType": "C",
            "stockType": "A",
            "stockDescription": "TEST STOCK",
            "stockShortName": "TEST",
            "currency": "EUR",
            "effectiveDate": "03/10/2026",
        }
    )
    fetcher._fetch_broker_txs = AsyncMock(return_value=[stock])
    fetcher._fetch_fund_txs = AsyncMock(return_value=[])

    result = await fetcher.transactions(set(), FetchOptions())

    assert result.investment == [stock]
    assert len(result.account) == 1
    assert result.account[0].type == TxType.OUTFLOW
    assert result.account[0].iban == "ES1234567890"
    fetcher._client.get_account_transactions.assert_awaited_once_with(
        "account-uuid",
        date(2026, 7, 4),
        offset=0,
        limit=100,
        to_date=date(2026, 10, 4),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("use_more_flag", [True, False])
async def test_account_fetch_paginates_using_response_metadata(
    account_fetcher, monkeypatch, use_more_flag
):
    monkeypatch.setattr(ing_module, "ACCOUNT_TXS_PAGE_SIZE", 2)
    first = _account_page(
        [_account_movement(1), _account_movement(2)],
        total=3,
        mayHasMoreElements=True,
    )
    last = _account_page([_account_movement(3)], total=3)
    if not use_more_flag:
        first.pop("mayHasMoreElements")
        last.pop("mayHasMoreElements")
    account_fetcher._client.get_account_transactions.side_effect = [first, last]

    txs = await account_fetcher._fetch_account_txs(
        [_account_product()], {}, set(), FetchOptions()
    )

    assert [tx.ref for tx in txs] == [
        f"account-uuid:{sequence}" for sequence in (1, 2, 3)
    ]
    requests = account_fetcher._client.get_account_transactions.await_args_list
    assert [request.kwargs["offset"] for request in requests] == [0, 2]
    assert all(request.kwargs["limit"] == 2 for request in requests)


@pytest.mark.asyncio
async def test_account_fetch_continues_after_known_refs_and_deduplicates_pages(
    account_fetcher, monkeypatch
):
    monkeypatch.setattr(ing_module, "ACCOUNT_TXS_PAGE_SIZE", 2)
    account_fetcher._client.get_account_transactions.side_effect = [
        _account_page(
            [_account_movement(1), _account_movement(2)],
            total=4,
            mayHasMoreElements=True,
        ),
        _account_page([_account_movement(2), _account_movement(3)], total=4),
    ]

    txs = await account_fetcher._fetch_account_txs(
        [_account_product()], {}, {"account-uuid:1"}, FetchOptions()
    )

    assert [tx.ref for tx in txs] == ["account-uuid:2", "account-uuid:3"]
    assert account_fetcher._client.get_account_transactions.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "threshold,deep,expected_from_date",
    [
        (None, False, date(2026, 7, 4)),
        (date(2026, 10, 1), False, date(2026, 9, 24)),
        (date(2025, 1, 1), False, date(2026, 7, 4)),
        (date(2026, 10, 10), False, date(2026, 9, 27)),
        (date(2026, 10, 1), True, date(2026, 7, 4)),
    ],
)
async def test_account_fetch_bounds_pointer_window_and_advances_after_success(
    account_fetcher, threshold, deep, expected_from_date
):
    options = _pointer_options(threshold, deep)
    account_fetcher._client.get_account_transactions.return_value = _account_page([])

    assert (
        await account_fetcher._fetch_account_txs(
            [_account_product()], {}, set(), options
        )
        == []
    )

    account_fetcher._client.get_account_transactions.assert_awaited_once_with(
        "account-uuid",
        expected_from_date,
        offset=0,
        limit=100,
        to_date=date(2026, 10, 4),
    )
    pointer = options.pointer_context.pointers["account_txs:ES1234567890"]
    assert pointer.threshold == date(2026, 10, 4)
    assert pointer.entity_id == ING.id
    assert pointer.entity_account_id == options.pointer_context.entity_account_id


@pytest.mark.asyncio
async def test_account_fetch_filters_dates_outside_requested_window(account_fetcher):
    account_fetcher._client.get_account_transactions.return_value = _account_page(
        [
            _account_movement(1, transactionDate="2026-07-03"),
            _account_movement(2, transactionDate="2026-07-04"),
            _account_movement(3, transactionDate="2026-10-04"),
            _account_movement(4, transactionDate="2026-10-05"),
        ]
    )

    txs = await account_fetcher._fetch_account_txs(
        [_account_product()], {}, set(), FetchOptions()
    )

    assert [tx.ref for tx in txs] == ["account-uuid:2", "account-uuid:3"]


@pytest.mark.asyncio
async def test_account_fetch_uses_currency_and_iban_from_each_account(account_fetcher):
    account_fetcher._client.get_account_transactions.side_effect = [
        _account_page([_account_movement(1)]),
        _account_page(
            [
                _account_movement(
                    1,
                    transactionId={
                        "productId": "savings-uuid",
                        "transactionSequence": 1,
                    },
                )
            ]
        ),
    ]
    products = [
        _account_product(),
        _account_product("savings-uuid", "SAVINGS_ACCOUNT", identifiers=[]),
    ]
    legacy = {"number-account-uuid": {"iban": "es98 7654 3210", "currency": "USD"}}
    options = _pointer_options()

    txs = await account_fetcher._fetch_account_txs(products, legacy, set(), options)

    assert [(tx.ref, tx.currency, tx.iban) for tx in txs] == [
        ("account-uuid:1", "USD", "ES9876543210"),
        ("savings-uuid:1", "EUR", None),
    ]
    assert set(options.pointer_context.pointers) == {
        "account_txs:ES9876543210",
        "account_txs:savings-uuid",
    }


@pytest.mark.asyncio
async def test_account_fetch_skips_suspended_missing_uuid_and_non_account_products(
    account_fetcher,
):
    products = [
        _account_product(statuses=[{"type": "PRODUCT_STATUS", "value": "SUSPENDED"}]),
        _account_product(uuid=None),
        _account_product(product_type="BROKER"),
        _account_product(product_type="CREDIT_CARD"),
    ]

    assert (
        await account_fetcher._fetch_account_txs(products, {}, set(), FetchOptions())
        == []
    )
    account_fetcher._client.get_account_transactions.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_page_does_not_advance_account_pointer(account_fetcher):
    options = _pointer_options(date(2026, 10, 1))
    pointer = options.pointer_context.pointers["account_txs:ES1234567890"]
    account_fetcher._client.get_account_transactions.side_effect = [
        _account_page([_account_movement(1)], total=2, mayHasMoreElements=True),
        RuntimeError("account page unavailable"),
    ]

    with pytest.raises(RuntimeError, match="account page unavailable"):
        await account_fetcher._fetch_account_txs(
            [_account_product()], {}, set(), options
        )

    assert options.pointer_context.pointers["account_txs:ES1234567890"] is pointer
    assert pointer.threshold == date(2026, 10, 1)


@pytest.mark.asyncio
async def test_account_fetch_uses_calendar_months_at_month_end(account_fetcher):
    ing_module.datetime.now.return_value = datetime(2026, 1, 31, tzinfo=tzlocal())
    account_fetcher._client.get_account_transactions.return_value = _account_page([])

    await account_fetcher._fetch_account_txs(
        [_account_product()], {}, set(), FetchOptions()
    )

    assert account_fetcher._client.get_account_transactions.await_args.args[1] == date(
        2025, 10, 31
    )


def _old_txs_options():
    return FetchOptions(two_factor_old_txs=True)


def _old_stage_options():
    return FetchOptions(two_factor_old_txs=True, stage=FetchStage.TWO_FACTOR_OLD_TXS)


def _sca_documentation(process_id="sec-1", code=ing_module.SCA_CIPHER_REQUEST_CODE):
    return {
        "acceptanceMethods": [
            {"code": code, "securityProcessId": process_id},
        ]
    }


@pytest.fixture
def sca_fetcher(account_fetcher, monkeypatch):
    monkeypatch.setattr(ing_module, "SCA_POLL_INTERVAL_SECONDS", 0.01)
    account_fetcher._client.supports_sca = MagicMock(return_value=True)
    account_fetcher._client.start_sca.return_value = _sca_documentation()
    account_fetcher._client.get_sca_status.return_value = {
        "scaStatus": 3,
        "resultCode": 0,
    }
    account_fetcher._client.synchronize_access_token.return_value = True
    return account_fetcher


async def _lock_older_movements(fetcher):
    fetcher._client.get_account_transactions.side_effect = [
        _account_page(
            [_account_movement(1), _account_movement(2)],
            total=2,
            mayHasMoreElements=True,
            moreSca=True,
        )
    ]
    return await fetcher._fetch_account_txs(
        [_account_product()], {}, set(), _old_txs_options()
    )


@pytest.mark.asyncio
async def test_old_txs_option_fetches_max_lookback_and_stores_locked_cursor(
    account_fetcher,
):
    txs = await _lock_older_movements(account_fetcher)

    assert [tx.ref for tx in txs] == ["account-uuid:1", "account-uuid:2"]
    account_fetcher._client.get_account_transactions.assert_awaited_once_with(
        "account-uuid",
        date(2026, 10, 4) - timedelta(days=ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS),
        offset=0,
        limit=100,
        to_date=date(2026, 10, 4),
    )
    cursor = account_fetcher._old_txs_cursors["account-uuid"]
    assert cursor.offset == 2
    assert cursor.iban == "ES1234567890"


@pytest.mark.asyncio
async def test_more_sca_stops_paging_without_cursor_when_option_disabled(
    account_fetcher,
):
    account_fetcher._client.get_account_transactions.side_effect = [
        _account_page(
            [_account_movement(1)], total=5, mayHasMoreElements=True, moreSca=True
        )
    ]

    txs = await account_fetcher._fetch_account_txs(
        [_account_product()], {}, set(), FetchOptions()
    )

    assert len(txs) == 1
    account_fetcher._client.get_account_transactions.assert_awaited_once()
    assert account_fetcher._old_txs_cursors == {}


@pytest.mark.asyncio
async def test_request_old_txs_code_skips_without_locked_cursors(sca_fetcher):
    assert await sca_fetcher.request_old_txs_code() is None
    sca_fetcher._client.start_sca.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_old_txs_code_skips_without_sca_session(sca_fetcher):
    await _lock_older_movements(sca_fetcher)
    sca_fetcher._client.supports_sca.return_value = False

    assert await sca_fetcher.request_old_txs_code() is None
    sca_fetcher._client.start_sca.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_old_txs_code_returns_in_app_confirmation(sca_fetcher):
    await _lock_older_movements(sca_fetcher)

    result = await sca_fetcher.request_old_txs_code()

    assert result.code == LoginResultCode.CODE_REQUESTED
    assert result.confirmation_type == LoginConfirmationType.IN_APP
    assert result.process_id == "sec-1"


@pytest.mark.asyncio
async def test_request_old_txs_code_rejects_unsupported_method(sca_fetcher):
    await _lock_older_movements(sca_fetcher)
    sca_fetcher._client.start_sca.return_value = _sca_documentation(code="otp")

    with pytest.raises(ValueError, match="otp"):
        await sca_fetcher.request_old_txs_code()


@pytest.mark.asyncio
async def test_confirm_old_txs_code_waits_for_approval_and_refreshes_token(
    sca_fetcher,
):
    await _lock_older_movements(sca_fetcher)
    await sca_fetcher.request_old_txs_code()
    sca_fetcher._client.get_sca_status.side_effect = [
        {"scaStatus": 1, "resultCode": 1},
        {"scaStatus": 3, "resultCode": 0},
    ]

    result = await sca_fetcher.confirm_old_txs_code(TwoFactor(process_id="sec-1"))

    assert result.code == LoginResultCode.CREATED
    assert sca_fetcher._client.get_sca_status.await_count == 2
    sca_fetcher._client.get_sca_status.assert_awaited_with("sec-1")
    sca_fetcher._client.confirm_sca.assert_awaited_once_with("sec-1")
    sca_fetcher._client.synchronize_access_token.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirm_old_txs_code_rejects_mismatched_process(sca_fetcher):
    await _lock_older_movements(sca_fetcher)
    await sca_fetcher.request_old_txs_code()

    result = await sca_fetcher.confirm_old_txs_code(TwoFactor(process_id="other"))

    assert result.code == LoginResultCode.NOT_LOGGED
    sca_fetcher._client.get_sca_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_old_txs_code_rejects_expired_request(sca_fetcher, monkeypatch):
    await _lock_older_movements(sca_fetcher)
    await sca_fetcher.request_old_txs_code()
    monkeypatch.setattr(ing_module, "OLD_TXS_SCA_TTL_SECONDS", -1)

    result = await sca_fetcher.confirm_old_txs_code(TwoFactor(process_id="sec-1"))

    assert result.code == LoginResultCode.NOT_LOGGED
    sca_fetcher._client.get_sca_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_old_txs_code_times_out_without_approval(
    sca_fetcher, monkeypatch
):
    await _lock_older_movements(sca_fetcher)
    await sca_fetcher.request_old_txs_code()
    monkeypatch.setattr(ing_module, "SCA_APPROVAL_TIMEOUT_SECONDS", 0.03)
    sca_fetcher._client.get_sca_status.return_value = {"scaStatus": 1}

    result = await sca_fetcher.confirm_old_txs_code(TwoFactor(process_id="sec-1"))

    assert result.code == LoginResultCode.NOT_LOGGED
    sca_fetcher._client.confirm_sca.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_old_txs_code_stops_when_cancelled(sca_fetcher, monkeypatch):
    await _lock_older_movements(sca_fetcher)
    await sca_fetcher.request_old_txs_code()
    monkeypatch.setattr(ing_module, "SCA_POLL_INTERVAL_SECONDS", 5)

    async def pending_status(_):
        sca_fetcher.cancel_login()
        return {"scaStatus": 1}

    sca_fetcher._client.get_sca_status.side_effect = pending_status

    result = await sca_fetcher.confirm_old_txs_code(TwoFactor(process_id="sec-1"))

    assert result.code == LoginResultCode.UNEXPECTED_ERROR
    assert result.message == "Approval cancelled by user."
    sca_fetcher._client.confirm_sca.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_old_txs_code_fails_without_new_access_token(sca_fetcher):
    await _lock_older_movements(sca_fetcher)
    await sca_fetcher.request_old_txs_code()
    sca_fetcher._client.synchronize_access_token.return_value = False

    result = await sca_fetcher.confirm_old_txs_code(TwoFactor(process_id="sec-1"))

    assert result.code == LoginResultCode.UNEXPECTED_ERROR
    assert sca_fetcher._sca_unlocked is False


@pytest.mark.asyncio
async def test_old_stage_resumes_cursor_without_cache_and_keeps_remaining_lock(
    sca_fetcher,
):
    await _lock_older_movements(sca_fetcher)
    await sca_fetcher.request_old_txs_code()
    await sca_fetcher.confirm_old_txs_code(TwoFactor(process_id="sec-1"))
    sca_fetcher._client.get_account_transactions.reset_mock()
    sca_fetcher._client.get_account_transactions.side_effect = [
        _account_page(
            [_account_movement(1), _account_movement(3, transactionDate="2025-01-10")],
            total=4,
            mayHasMoreElements=True,
        ),
        _account_page(
            [_account_movement(4, transactionDate="2024-12-01")],
            total=5,
            mayHasMoreElements=True,
            moreSca=True,
        ),
    ]

    result = await sca_fetcher.transactions({"account-uuid:1"}, _old_stage_options())

    assert result.investment == []
    assert [tx.ref for tx in result.account] == ["account-uuid:3", "account-uuid:4"]
    requests = sca_fetcher._client.get_account_transactions.await_args_list
    assert [request.kwargs["offset"] for request in requests] == [2, 4]
    assert all(request.kwargs["cache_read"] is False for request in requests)
    sca_fetcher._client.get_position.assert_not_awaited()
    assert sca_fetcher._old_txs_cursors["account-uuid"].offset == 5
    assert sca_fetcher._sca_unlocked is False


@pytest.mark.asyncio
async def test_old_stage_without_approval_returns_no_transactions(sca_fetcher):
    await _lock_older_movements(sca_fetcher)
    sca_fetcher._client.get_account_transactions.reset_mock()

    result = await sca_fetcher.transactions(set(), _old_stage_options())

    assert result.account == []
    sca_fetcher._client.get_account_transactions.assert_not_awaited()


def test_map_movement_maps_transfer_out():
    tx = _map_movement_to_stock_tx(
        {
            "uuid": "ts-ref",
            "stockType": "A",
            "stockDescription": "LIBERBANK",
            "operationType": "TS",
            "stockName": "ES0168675009",
            "stockShortName": "LBK",
            "titlesNumber": 2044,
            "operationChange": 0.00,
            "operationAmount": 0.00,
            "amount": 0.00,
            "commission": 0.00,
            "currency": "EUR",
            "effectiveDate": "18/11/2015",
            "description": "TRASPASO SALIDA",
        }
    )

    assert tx is not None
    assert tx.ref == "ts-ref"
    assert tx.type == TxType.TRANSFER_OUT
    assert tx.isin == "ES0168675009"
    assert tx.shares == Dezimal("2044")
    assert tx.amount == Dezimal("0")
    assert tx.net_amount == Dezimal("0")
    assert tx.fees == Dezimal("0")
