import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import infrastructure.client.entity.financial.cajamar.cajamar_fetcher as cajamar_module
from domain.entity_login import LoginConfirmationType, LoginResultCode, TwoFactor
from domain.fetch_pointer import FetchPointerContext
from domain.fetch_result import FetchOptions, FetchStage
from domain.transactions import ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS
from infrastructure.client.entity.financial.cajamar.cajamar_fetcher import (
    CajamarFetcher,
)

IBAN_1 = "ES7630580000000000000001"
IBAN_2 = "ES7630580000000000000002"
IBAN_3 = "ES7630580000000000000003"


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(cajamar_module, "SIGNATURE_POLL_INTERVAL_SECONDS", 0.01)


def _options(two_factor_old_txs=True, stage=FetchStage.MAIN):
    return FetchOptions(
        pointer_context=FetchPointerContext(
            entity_id=uuid4(), entity_account_id=uuid4(), pointers={}
        ),
        two_factor_old_txs=two_factor_old_txs,
        stage=stage,
    )


def _old_stage_options():
    return _options(stage=FetchStage.TWO_FACTOR_OLD_TXS)


def _movement(id_doc, tx_date, amount, description):
    return {
        "description": description,
        "date": tx_date.isoformat(),
        "currency": "EUR",
        "amount": amount,
        "documentId": str(uuid4().int)[:20],
        "idDoc": id_doc,
        "deferId": str(uuid4().int)[:20],
    }


def _page(movements, page_number=1, num_pages=1):
    return {
        "accountTransactionsPagination": {
            "dataList": movements,
            "pagination": {
                "pageNumber": page_number,
                "numPages": num_pages,
                "pageSize": 16,
                "total": len(movements),
            },
        }
    }


def _challenge(optk):
    return {
        "type": "PIN",
        "transactionReference": "ref",
        "smsSignatureReference": "444900439",
        "operationData": [{"concept": "ACCOUNT", "value": IBAN_1}],
        "optk": optk,
    }


def _fetcher(accounts, undated, dated):
    fetcher = CajamarFetcher()
    fetcher._client = MagicMock()
    fetcher._client.get_position = AsyncMock(return_value={"accounts": accounts})

    async def get_account_txs(account_id, page_num=1, page_size=16, **kwargs):
        if kwargs.get("date_from"):
            return dated[account_id].pop(0)
        return undated[account_id].pop(0)

    fetcher._client.get_account_txs = AsyncMock(side_effect=get_account_txs)
    fetcher._client.sign_account_txs = AsyncMock(return_value=None)
    return fetcher


def _dated_calls(fetcher):
    return [
        (call.args[0], call.args[1])
        for call in fetcher._client.get_account_txs.await_args_list
        if call.kwargs.get("date_from")
    ]


@pytest.mark.asyncio
async def test_main_requests_signature_for_first_account():
    today = date.today()
    recent = _movement("1", today, -10.0, "RECIBO")
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([recent])]},
        {"acc-1": [_challenge("optk-1")]},
    )

    txs = (await fetcher.transactions(set(), _options())).account
    result = await fetcher.request_old_txs_code()

    assert [tx.name for tx in txs] == ["RECIBO"]
    assert result.code == LoginResultCode.CODE_REQUESTED
    assert result.confirmation_type == LoginConfirmationType.IN_APP
    assert result.process_id == "optk-1"
    dated_call = fetcher._client.get_account_txs.await_args_list[-1]
    assert dated_call.kwargs == {
        "date_from": today - timedelta(days=ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS),
        "date_to": today,
    }
    assert dated_call.args == ("acc-1", 1, 16)


@pytest.mark.asyncio
async def test_main_without_option_does_not_request_signature():
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([])]},
        {},
    )

    await fetcher.transactions(set(), _options(two_factor_old_txs=False))

    assert await fetcher.request_old_txs_code() is None
    assert _dated_calls(fetcher) == []


@pytest.mark.asyncio
async def test_main_includes_dated_movements_when_no_signature_required():
    today = date.today()
    recent = _movement("1", today, -10.0, "RECIBO")
    old = _movement("2", today - timedelta(days=200), -30.0, "OLD")
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([recent])]},
        {"acc-1": [_page([recent, old])]},
    )

    txs = (await fetcher.transactions(set(), _options())).account

    assert [tx.name for tx in txs] == ["RECIBO", "OLD"]
    assert await fetcher.request_old_txs_code() is None


@pytest.mark.asyncio
async def test_main_ignores_dated_request_errors():
    today = date.today()
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([_movement("1", today, -10.0, "RECIBO")])]},
        {},
    )

    txs = (await fetcher.transactions(set(), _options())).account

    assert [tx.name for tx in txs] == ["RECIBO"]
    assert await fetcher.request_old_txs_code() is None


@pytest.mark.asyncio
async def test_confirm_polls_signature_and_old_stage_pages_range():
    today = date.today()
    recent = _movement("1", today, -10.0, "RECIBO")
    old_1 = _movement("2", today - timedelta(days=150), -20.0, "OLD 1")
    old_2 = _movement("3", today - timedelta(days=400), 50.0, "OLD 2")
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([recent])]},
        {
            "acc-1": [
                _challenge("optk-1"),
                _page([old_2], page_number=2, num_pages=2),
            ]
        },
    )
    main_txs = (await fetcher.transactions(set(), _options())).account
    await fetcher.request_old_txs_code()
    fetcher._client.sign_account_txs = AsyncMock(
        side_effect=[None, None, _page([recent, old_1], num_pages=2)]
    )

    confirm = await fetcher.confirm_old_txs_code(TwoFactor(process_id="optk-1"))
    old_txs = (
        await fetcher.transactions({main_txs[0].ref}, _old_stage_options())
    ).account

    assert confirm.code == LoginResultCode.CREATED
    assert fetcher._client.sign_account_txs.await_count == 3
    fetcher._client.sign_account_txs.assert_awaited_with("acc-1", "optk-1")
    assert [tx.name for tx in old_txs] == ["OLD 1", "OLD 2"]
    assert {tx.iban for tx in old_txs} == {IBAN_1}
    assert _dated_calls(fetcher) == [("acc-1", 1), ("acc-1", 2)]
    assert await fetcher.request_old_txs_code() is None


@pytest.mark.asyncio
async def test_old_stage_continues_with_next_accounts():
    today = date.today()
    old_1 = _movement("1", today - timedelta(days=150), -20.0, "OLD 1")
    old_2 = _movement("2", today - timedelta(days=160), -21.0, "OLD 2")
    fetcher = _fetcher(
        [
            {"id": "acc-1", "iban": IBAN_1},
            {"id": "acc-2", "iban": IBAN_2},
            {"id": "acc-3", "iban": IBAN_3},
        ],
        {"acc-1": [_page([])], "acc-2": [_page([])], "acc-3": [_page([])]},
        {
            "acc-1": [_challenge("optk-1")],
            "acc-2": [_page([old_2])],
            "acc-3": [_challenge("optk-3")],
        },
    )
    await fetcher.transactions(set(), _options())
    await fetcher.request_old_txs_code()
    fetcher._client.sign_account_txs = AsyncMock(return_value=_page([old_1]))

    await fetcher.confirm_old_txs_code(TwoFactor(process_id="optk-1"))
    old_txs = (await fetcher.transactions(set(), _old_stage_options())).account
    next_request = await fetcher.request_old_txs_code()

    assert [(tx.name, tx.iban) for tx in old_txs] == [
        ("OLD 1", IBAN_1),
        ("OLD 2", IBAN_2),
    ]
    assert next_request.process_id == "optk-3"
    assert next_request.confirmation_type == LoginConfirmationType.IN_APP


@pytest.mark.asyncio
async def test_confirm_rejects_mismatched_process_id():
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([])]},
        {"acc-1": [_challenge("optk-1")]},
    )
    await fetcher.transactions(set(), _options())
    await fetcher.request_old_txs_code()

    result = await fetcher.confirm_old_txs_code(TwoFactor(process_id="other"))

    assert result.code == LoginResultCode.NOT_LOGGED
    fetcher._client.sign_account_txs.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_rejects_expired_signature(monkeypatch):
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([])]},
        {"acc-1": [_challenge("optk-1")]},
    )
    await fetcher.transactions(set(), _options())
    await fetcher.request_old_txs_code()
    monkeypatch.setattr(cajamar_module, "OLD_TXS_SIGNATURE_TTL_SECONDS", -1)

    result = await fetcher.confirm_old_txs_code(TwoFactor(process_id="optk-1"))

    assert result.code == LoginResultCode.NOT_LOGGED
    fetcher._client.sign_account_txs.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_times_out_when_never_signed(monkeypatch):
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([])]},
        {"acc-1": [_challenge("optk-1")]},
    )
    await fetcher.transactions(set(), _options())
    await fetcher.request_old_txs_code()
    monkeypatch.setattr(cajamar_module, "SIGNATURE_APPROVAL_TIMEOUT_SECONDS", 0.05)

    result = await fetcher.confirm_old_txs_code(TwoFactor(process_id="optk-1"))
    old_txs = (await fetcher.transactions(set(), _old_stage_options())).account

    assert result.code == LoginResultCode.NOT_LOGGED
    assert fetcher._client.sign_account_txs.await_count >= 1
    assert old_txs == []


@pytest.mark.asyncio
async def test_confirm_stops_when_cancelled(monkeypatch):
    monkeypatch.setattr(cajamar_module, "SIGNATURE_POLL_INTERVAL_SECONDS", 5)
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([])]},
        {"acc-1": [_challenge("optk-1")]},
    )
    await fetcher.transactions(set(), _options())
    await fetcher.request_old_txs_code()

    confirm = asyncio.create_task(
        fetcher.confirm_old_txs_code(TwoFactor(process_id="optk-1"))
    )
    await asyncio.sleep(0.01)
    fetcher.cancel_login()
    result = await asyncio.wait_for(confirm, timeout=1)

    assert result.code == LoginResultCode.UNEXPECTED_ERROR
    fetcher._client.sign_account_txs.assert_not_awaited()
