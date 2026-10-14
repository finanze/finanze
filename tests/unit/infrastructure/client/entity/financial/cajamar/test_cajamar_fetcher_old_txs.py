from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.entity_login import LoginResultCode
from domain.fetch_pointer import FetchPointerContext
from domain.fetch_result import FetchOptions
from domain.transactions import ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS
from infrastructure.client.entity.financial.cajamar.cajamar_client import (
    CajamarSignatureRequired,
)
from infrastructure.client.entity.financial.cajamar.cajamar_fetcher import (
    CajamarFetcher,
)

IBAN_1 = "ES7630580000000000000001"
IBAN_2 = "ES7630580000000000000002"


def _options(two_factor_old_txs=True):
    return FetchOptions(
        pointer_context=FetchPointerContext(
            entity_id=uuid4(), entity_account_id=uuid4(), pointers={}
        ),
        two_factor_old_txs=two_factor_old_txs,
    )


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
            response = dated[account_id].pop(0)
        else:
            response = undated[account_id].pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    fetcher._client.get_account_txs = AsyncMock(side_effect=get_account_txs)
    return fetcher


def _dated_calls(fetcher):
    return [
        (call.args[0], call.args[1])
        for call in fetcher._client.get_account_txs.await_args_list
        if call.kwargs.get("date_from")
    ]


@pytest.mark.asyncio
async def test_main_requests_dated_range_per_account():
    today = date.today()
    recent = _movement("1", today, -10.0, "RECIBO")
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([recent])]},
        {"acc-1": [_page([recent])]},
    )

    txs = (await fetcher.transactions(set(), _options())).account

    assert [tx.name for tx in txs] == ["RECIBO"]
    assert await fetcher.request_old_txs_code() is None
    dated_call = fetcher._client.get_account_txs.await_args_list[-1]
    assert dated_call.kwargs == {
        "date_from": today - timedelta(days=ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS),
        "date_to": today,
    }
    assert dated_call.args == ("acc-1", 1, 16)


@pytest.mark.asyncio
async def test_signature_required_stops_old_movements_and_reports_requirement():
    today = date.today()
    recent = _movement("1", today, -10.0, "RECIBO")
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}, {"id": "acc-2", "iban": IBAN_2}],
        {"acc-1": [_page([recent])], "acc-2": [_page([])]},
        {"acc-1": [CajamarSignatureRequired("SGN000")], "acc-2": [_page([])]},
    )

    txs = (await fetcher.transactions(set(), _options())).account
    result = await fetcher.request_old_txs_code()

    assert [tx.name for tx in txs] == ["RECIBO"]
    assert _dated_calls(fetcher) == [("acc-1", 1)]
    assert result.code == LoginResultCode.NOT_LOGGED
    assert result.details == {"oldTxsRequirement": "MAIN_DEVICE_SIGNATURE"}
    assert await fetcher.request_old_txs_code() is None


@pytest.mark.asyncio
async def test_optk_challenge_is_treated_as_signature_required():
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}, {"id": "acc-2", "iban": IBAN_2}],
        {"acc-1": [_page([])], "acc-2": [_page([])]},
        {"acc-1": [_challenge("optk-1")], "acc-2": [_page([])]},
    )

    await fetcher.transactions(set(), _options())
    result = await fetcher.request_old_txs_code()

    assert _dated_calls(fetcher) == [("acc-1", 1)]
    assert result.details == {"oldTxsRequirement": "MAIN_DEVICE_SIGNATURE"}


@pytest.mark.asyncio
async def test_new_transactions_fetch_clears_previous_signature_requirement():
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([]), _page([])]},
        {"acc-1": [CajamarSignatureRequired("SGN000")]},
    )

    await fetcher.transactions(set(), _options())
    await fetcher.transactions(set(), _options(two_factor_old_txs=False))

    assert await fetcher.request_old_txs_code() is None


@pytest.mark.asyncio
async def test_main_pages_old_movements_and_skips_known():
    today = date.today()
    recent = _movement("1", today, -10.0, "RECIBO")
    old_1 = _movement("2", today - timedelta(days=150), -20.0, "OLD 1")
    old_2 = _movement("3", today - timedelta(days=400), 50.0, "OLD 2")
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}],
        {"acc-1": [_page([recent])]},
        {
            "acc-1": [
                _page([recent, old_1], num_pages=2),
                _page([old_2], page_number=2, num_pages=2),
            ]
        },
    )

    txs = (await fetcher.transactions(set(), _options())).account

    assert [tx.name for tx in txs] == ["RECIBO", "OLD 1", "OLD 2"]
    assert {tx.iban for tx in txs} == {IBAN_1}
    assert _dated_calls(fetcher) == [("acc-1", 1), ("acc-1", 2)]
    assert await fetcher.request_old_txs_code() is None


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
    old = _movement("2", today - timedelta(days=200), -30.0, "OLD")
    fetcher = _fetcher(
        [{"id": "acc-1", "iban": IBAN_1}, {"id": "acc-2", "iban": IBAN_2}],
        {
            "acc-1": [_page([_movement("1", today, -10.0, "RECIBO")])],
            "acc-2": [_page([])],
        },
        {"acc-1": [RuntimeError("boom")], "acc-2": [_page([old])]},
    )

    txs = (await fetcher.transactions(set(), _options())).account

    assert [(tx.name, tx.iban) for tx in txs] == [
        ("RECIBO", IBAN_1),
        ("OLD", IBAN_2),
    ]
    assert await fetcher.request_old_txs_code() is None
