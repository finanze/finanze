from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.dezimal import Dezimal
from domain.fetch_pointer import FetchPointer, FetchPointerContext
from domain.fetch_result import FetchOptions
from domain.native_entities import CAJAMAR
from domain.transactions import TxType
from infrastructure.client.entity.financial.cajamar.cajamar_fetcher import (
    ACCOUNT_TXS_POINTER,
    CajamarFetcher,
)

IBAN = "ES7630580000000000000001"
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


def _movement(id_doc, tx_date, amount, description, document_id=None):
    return {
        "description": description,
        "date": tx_date.isoformat(),
        "currency": "EUR",
        "amount": amount,
        "balance": 100.0,
        "documentId": document_id or str(uuid4().int)[:20],
        "receiptInd": "false",
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


def _fetcher(pages):
    fetcher = CajamarFetcher()
    fetcher._client = MagicMock()
    fetcher._client.get_position = AsyncMock(
        return_value={
            "accounts": [{"id": "acc-token", "iban": "ES76 3058 0000 0000 0000 0001"}]
        }
    )
    fetcher._client.get_account_txs = AsyncMock(side_effect=pages)
    return fetcher


@pytest.mark.asyncio
async def test_paginates_and_maps_movements():
    today = date.today()
    fetcher = _fetcher(
        [
            _page(
                [
                    _movement(
                        "1",
                        today,
                        -20.36,
                        "TRASPASO      CUOTA MENSUAL CLUB SEGUROS   ",
                    ),
                    _movement(
                        "2", today - timedelta(days=1), 4329.48, "NOMINA NOMINAS"
                    ),
                ],
                page_number=1,
                num_pages=2,
            ),
            _page(
                [
                    _movement(
                        "3", today - timedelta(days=5), -313.67, "AMORTIZACION PRESTAMO"
                    ),
                    _movement(
                        "3", today - timedelta(days=5), -224.14, "INTERESES DE PRESTAMO"
                    ),
                ],
                page_number=2,
                num_pages=2,
            ),
        ]
    )
    options = _options()

    result = await fetcher.transactions(set(), options)

    txs = result.account
    assert [(tx.type, tx.amount) for tx in txs] == [
        (TxType.OUTFLOW, Dezimal("20.36")),
        (TxType.INFLOW, Dezimal("4329.48")),
        (TxType.OUTFLOW, Dezimal("313.67")),
        (TxType.OUTFLOW, Dezimal("224.14")),
    ]
    assert txs[0].name == "TRASPASO CUOTA MENSUAL CLUB SEGUROS"
    assert txs[0].entity == CAJAMAR
    assert txs[0].date.tzinfo is not None
    assert {tx.iban for tx in txs} == {IBAN}
    assert len({tx.ref for tx in txs}) == 4
    fetcher._client.get_account_txs.assert_any_await("acc-token", 2, 16)
    assert options.pointer_context.pointers[POINTER_KEY].threshold == today


@pytest.mark.asyncio
async def test_refs_are_stable_across_requests():
    today = date.today()
    first = _fetcher(
        [_page([_movement("9", today, -13.0, "RECIBO DIGI", document_id="111")])]
    )
    second = _fetcher(
        [_page([_movement("9", today, -13.0, "RECIBO DIGI", document_id="222")])]
    )

    first_txs = (await first.transactions(set(), _options())).account
    second_txs = (await second.transactions(set(), _options())).account

    assert first_txs[0].ref == second_txs[0].ref


@pytest.mark.asyncio
async def test_stops_at_registered_movement():
    today = date.today()
    known = _movement("5", today - timedelta(days=2), -6.0, "TARJETA")
    probe = _fetcher([_page([known])])
    known_ref = (await probe.transactions(set(), _options())).account[0].ref

    fetcher = _fetcher(
        [
            _page(
                [_movement("6", today, 60.0, "TRANSF. INMEDIATA RECIBIDA"), known],
                num_pages=3,
            )
        ]
    )

    txs = (await fetcher.transactions({known_ref}, _options())).account

    assert [tx.name for tx in txs] == ["TRANSF. INMEDIATA RECIBIDA"]
    assert fetcher._client.get_account_txs.await_count == 1


@pytest.mark.asyncio
async def test_pointer_limits_history():
    today = date.today()
    fetcher = _fetcher(
        [
            _page(
                [
                    _movement("7", today, -165.0, "RECIBO CDAD PROP"),
                    _movement("8", today - timedelta(days=10), -73.92, "RECIBO AYTO"),
                ],
                num_pages=5,
            )
        ]
    )

    txs = (
        await fetcher.transactions(
            set(), _options(pointer_threshold=today - timedelta(days=3))
        )
    ).account

    assert [tx.name for tx in txs] == ["RECIBO CDAD PROP"]
    assert fetcher._client.get_account_txs.await_count == 1
