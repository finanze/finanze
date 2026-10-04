from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.dezimal import Dezimal
from domain.fetch_pointer import FetchPointer, FetchPointerContext
from domain.fetch_result import FetchOptions
from domain.transactions import TxType
from infrastructure.client.entity.financial.unicaja.unicaja_fetcher import (
    ACCOUNT_TXS_POINTER,
    UnicajaFetcher,
)

IBAN = "ES9121000418450200051332"


def _options(pointer_threshold=None):
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
    return FetchOptions(pointer_context=context)


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
