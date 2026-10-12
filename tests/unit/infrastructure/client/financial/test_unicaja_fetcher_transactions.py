from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.dezimal import Dezimal
from domain.entity_login import LoginResultCode, TwoFactor
from domain.fetch_pointer import FetchPointer, FetchPointerContext
from domain.fetch_result import FetchOptions, FetchStage
from domain.transactions import TxType
from infrastructure.client.entity.financial.unicaja.unicaja_fetcher import (
    ACCOUNT_TXS_POINTER,
    UnicajaFetcher,
)

IBAN = "ES9121000418450200051332"


def _options(pointer_threshold=None, two_factor_old_txs=False):
    context = FetchPointerContext(
        entity_id=uuid4(), entity_account_id=uuid4(), pointers={}
    )
    if pointer_threshold:
        key = f"{ACCOUNT_TXS_POINTER}:{IBAN}"
        context.pointers[key] = FetchPointer(
            entity_id=context.entity_id,
            entity_account_id=context.entity_account_id,
            key=key,
            threshold=pointer_threshold,
        )
    return FetchOptions(pointer_context=context, two_factor_old_txs=two_factor_old_txs)


def _movement(num, tx_date, amount, concept="Concept"):
    return {
        "fechaOperacion": tx_date.isoformat(),
        "concepto": concept,
        "numMovimiento": str(num),
        "importeMovimiento": {"cantidad": amount, "moneda": "EUR"},
        "categoria": "OTROS",
    }


def _fetcher(pages):
    fetcher = UnicajaFetcher()
    fetcher._client = MagicMock()
    fetcher._client.list_accounts = AsyncMock(
        return_value={"cuentas": [{"ppp": "001", "iban": IBAN}]}
    )
    fetcher._client.get_account_movements = AsyncMock(side_effect=pages)
    return fetcher


@pytest.mark.asyncio
async def test_paginates_until_no_more_movements_and_maps_sign():
    today = date.today()
    fetcher = _fetcher(
        [
            {
                "movimientos": [
                    _movement(10, today, "-25.50", "Supermercado"),
                    _movement(9, today - timedelta(days=1), "1200", "Nomina"),
                ],
                "masMovimientos": {
                    "indMasMovimientos": "S",
                    "indOTP": "N",
                    "ultimoSaldo": {"cantidad": 283.57},
                    "numUltimoMovimiento": 9,
                },
            },
            {
                "movimientos": [_movement(8, today - timedelta(days=2), "0")],
                "masMovimientos": {"indMasMovimientos": "N"},
            },
        ]
    )
    options = _options()

    result = await fetcher.transactions(set(), options)

    assert [(tx.ref, tx.type, tx.amount) for tx in result.account] == [
        (f"{IBAN}:10", TxType.OUTFLOW, Dezimal("25.50")),
        (f"{IBAN}:9", TxType.INFLOW, Dezimal("1200")),
    ]
    assert {tx.iban for tx in result.account} == {IBAN}
    second_call = fetcher._client.get_account_movements.await_args_list[1]
    assert second_call.args == ("001", "283.57", "9")
    pointer = options.pointer_context.pointers[f"{ACCOUNT_TXS_POINTER}:{IBAN}"]
    assert pointer.threshold == today


@pytest.mark.asyncio
async def test_stops_when_otp_is_required():
    today = date.today()
    fetcher = _fetcher(
        [
            {
                "movimientos": [_movement(1, today, "-5")],
                "masMovimientos": {
                    "indMasMovimientos": "S",
                    "indOTP": "S",
                    "ultimoSaldo": {"cantidad": "1"},
                    "numUltimoMovimiento": "1",
                },
            }
        ]
    )

    result = await fetcher.transactions(set(), _options())

    assert len(result.account) == 1
    assert fetcher._client.get_account_movements.await_count == 1


@pytest.mark.asyncio
async def test_stops_at_known_refs_and_pointer_date():
    today = date.today()
    fetcher = _fetcher(
        [
            {
                "movimientos": [
                    _movement(3, today, "-5"),
                    _movement(2, today - timedelta(days=1), "-6"),
                    _movement(1, today - timedelta(days=10), "-7"),
                ],
                "masMovimientos": {
                    "indMasMovimientos": "S",
                    "ultimoSaldo": {"cantidad": "1"},
                    "numUltimoMovimiento": "1",
                },
            }
        ]
    )

    result = await fetcher.transactions(
        {f"{IBAN}:2"}, _options(pointer_threshold=today - timedelta(days=3))
    )

    assert [tx.ref for tx in result.account] == [f"{IBAN}:3"]
    assert fetcher._client.get_account_movements.await_count == 1


def _otp_page(movements, balance="271.93", last="1581"):
    return {
        "movimientos": movements,
        "masMovimientos": {
            "indMasMovimientos": "S",
            "indOTP": "S",
            "ultimoSaldo": {"cantidad": balance},
            "numUltimoMovimiento": last,
        },
    }


def _with_signature(fetcher, signed=True):
    fetcher._client.simulate_movements_signature = AsyncMock(
        return_value={
            "coordenada": "**",
            "telefono": "******447",
            "referencia": "088926",
        }
    )
    fetcher._client.sign_movements = AsyncMock(return_value=signed)
    return fetcher


@pytest.mark.asyncio
async def test_otp_boundary_without_option_requests_no_code():
    today = date.today()
    fetcher = _with_signature(_fetcher([_otp_page([_movement(1, today, "-5")])]))

    await fetcher.transactions(set(), _options())

    assert await fetcher.request_old_txs_code() is None
    fetcher._client.simulate_movements_signature.assert_not_awaited()


@pytest.mark.asyncio
async def test_old_txs_option_pages_past_known_refs_until_otp():
    today = date.today()
    fetcher = _with_signature(
        _fetcher(
            [
                {
                    "movimientos": [
                        _movement(3, today, "-5"),
                        _movement(2, today - timedelta(days=1), "-6"),
                    ],
                    "masMovimientos": {
                        "indMasMovimientos": "S",
                        "ultimoSaldo": {"cantidad": "10"},
                        "numUltimoMovimiento": "2",
                    },
                },
                _otp_page([_movement(1, today - timedelta(days=80), "-7")]),
            ]
        )
    )
    options = _options(
        pointer_threshold=today - timedelta(days=1), two_factor_old_txs=True
    )

    result = await fetcher.transactions({f"{IBAN}:2"}, options)

    assert [tx.ref for tx in result.account] == [f"{IBAN}:3", f"{IBAN}:1"]
    assert fetcher._client.get_account_movements.await_count == 2
    pointer = options.pointer_context.pointers[f"{ACCOUNT_TXS_POINTER}:{IBAN}"]
    assert pointer.threshold == today

    code_request = await fetcher.request_old_txs_code()

    assert code_request.code == LoginResultCode.CODE_REQUESTED
    assert code_request.process_id == "088926"
    assert code_request.message == "******447"
    assert code_request.details == {"pinLength": 6, "pinChannel": "SMS"}
    fetcher._client.simulate_movements_signature.assert_awaited_once_with("001")


@pytest.mark.asyncio
async def test_old_txs_stage_resumes_from_otp_cursor_without_pointer_update():
    today = date.today()
    fetcher = _with_signature(
        _fetcher(
            [
                _otp_page([_movement(5, today, "-5")]),
                {
                    "movimientos": [
                        _movement(4, today - timedelta(days=120), "-6"),
                        _movement(3, today - timedelta(days=200), "-7"),
                    ],
                    "masMovimientos": {"indMasMovimientos": "N"},
                },
            ]
        )
    )
    await fetcher.transactions(set(), _options(two_factor_old_txs=True))
    code_request = await fetcher.request_old_txs_code()

    confirm = await fetcher.confirm_old_txs_code(
        TwoFactor(code="282334", process_id=code_request.process_id)
    )
    old_options = _options(two_factor_old_txs=True)
    old_options.stage = FetchStage.TWO_FACTOR_OLD_TXS
    result = await fetcher.transactions({f"{IBAN}:3"}, old_options)

    assert confirm.code == LoginResultCode.CREATED
    fetcher._client.sign_movements.assert_awaited_once_with("001", "**", "282334")
    assert [tx.ref for tx in result.account] == [f"{IBAN}:4"]
    resume_call = fetcher._client.get_account_movements.await_args_list[1]
    assert resume_call.args == ("001", "271.93", "1581")
    assert old_options.pointer_context.pointers == {}
    assert await fetcher.request_old_txs_code() is None


@pytest.mark.asyncio
async def test_old_txs_stage_continues_when_otp_marker_remains_after_signing():
    today = date.today()
    fetcher = _with_signature(
        _fetcher(
            [
                _otp_page([_movement(5, today, "-5")]),
                _otp_page([_movement(4, today - timedelta(days=120), "-6")], "50", "4"),
                {
                    "movimientos": [_movement(3, today - timedelta(days=200), "-7")],
                    "masMovimientos": {"indMasMovimientos": "N"},
                },
            ]
        )
    )
    await fetcher.transactions(set(), _options(two_factor_old_txs=True))
    await fetcher.request_old_txs_code()
    await fetcher.confirm_old_txs_code(TwoFactor(code="111111", process_id="088926"))

    old_options = _options()
    old_options.stage = FetchStage.TWO_FACTOR_OLD_TXS
    result = await fetcher.transactions(set(), old_options)

    assert [tx.ref for tx in result.account] == [f"{IBAN}:4", f"{IBAN}:3"]
    assert fetcher._client.get_account_movements.await_args_list[2].args == (
        "001",
        "50",
        "4",
    )
    assert await fetcher.request_old_txs_code() is None
    fetcher._client.simulate_movements_signature.assert_awaited_once_with("001")


@pytest.mark.asyncio
async def test_old_txs_stage_requests_next_account_code_after_finishing_first():
    today = date.today()
    second_iban = "ES6621000418401234567891"
    fetcher = _with_signature(
        _fetcher(
            [
                _otp_page([_movement(5, today, "-5")]),
                _otp_page([_movement(7, today, "-8")], "75", "7"),
                {
                    "movimientos": [_movement(4, today - timedelta(days=120), "-6")],
                    "masMovimientos": {"indMasMovimientos": "N"},
                },
                {
                    "movimientos": [_movement(6, today - timedelta(days=200), "-9")],
                    "masMovimientos": {"indMasMovimientos": "N"},
                },
            ]
        )
    )
    fetcher._client.list_accounts.return_value = {
        "cuentas": [{"ppp": "001", "iban": IBAN}, {"ppp": "002", "iban": second_iban}]
    }
    fetcher._client.simulate_movements_signature.side_effect = [
        {"coordenada": "**", "telefono": "******447", "referencia": "ref-1"},
        {"coordenada": "**", "telefono": "******447", "referencia": "ref-2"},
    ]
    await fetcher.transactions(set(), _options(two_factor_old_txs=True))
    first_request = await fetcher.request_old_txs_code()
    await fetcher.confirm_old_txs_code(
        TwoFactor(code="111111", process_id=first_request.process_id)
    )
    old_options = FetchOptions(stage=FetchStage.TWO_FACTOR_OLD_TXS)

    first_result = await fetcher.transactions(set(), old_options)
    second_request = await fetcher.request_old_txs_code()

    assert [tx.ref for tx in first_result.account] == [f"{IBAN}:4"]
    assert second_request.process_id == "ref-2"
    assert [
        signature_call.args
        for signature_call in fetcher._client.simulate_movements_signature.await_args_list
    ] == [("001",), ("002",)]
    await fetcher.confirm_old_txs_code(
        TwoFactor(code="222222", process_id=second_request.process_id)
    )
    second_result = await fetcher.transactions(set(), old_options)

    assert [tx.ref for tx in second_result.account] == [f"{second_iban}:6"]
    assert fetcher._client.get_account_movements.await_args_list[3].args == (
        "002",
        "75",
        "7",
    )
    assert await fetcher.request_old_txs_code() is None


@pytest.mark.asyncio
async def test_confirm_old_txs_code_handles_invalid_and_missing_requests():
    today = date.today()
    fetcher = _with_signature(
        _fetcher([_otp_page([_movement(5, today, "-5")])]), signed=False
    )

    missing = await fetcher.confirm_old_txs_code(TwoFactor(code="1"))
    await fetcher.transactions(set(), _options(two_factor_old_txs=True))
    await fetcher.request_old_txs_code()
    mismatch = await fetcher.confirm_old_txs_code(
        TwoFactor(code="1", process_id="other")
    )
    await fetcher.request_old_txs_code()
    invalid = await fetcher.confirm_old_txs_code(
        TwoFactor(code="1", process_id="088926")
    )

    assert missing.code == LoginResultCode.NOT_LOGGED
    assert mismatch.code == LoginResultCode.NOT_LOGGED
    assert invalid.code == LoginResultCode.INVALID_CODE
    assert fetcher._pending_signature is not None
