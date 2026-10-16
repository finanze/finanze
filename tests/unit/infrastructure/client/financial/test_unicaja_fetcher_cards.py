from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.dezimal import Dezimal
from domain.global_position import ProductType
from infrastructure.client.entity.financial.unicaja.unicaja_fetcher import (
    UnicajaFetcher,
)

IBAN = "ES5421037028210030026420"


def _card(ending, ppp):
    return {
        "ibancuenta": IBAN,
        "tipotarjeta": "MASTERCARD DEBITO",
        "alias": "",
        "numtarjeta": f"5540 02** **** {ending}",
        "estado": "E",
        "codtipotarjeta": "1",
        "limite": {"cantidad": 1000.0, "moneda": "EUR"},
        "pagadoMesActual": {"cantidad": 25.0, "moneda": "EUR"},
        "ppp": ppp,
    }


def _card_details(disposed):
    return {"datosCredito": {"importeDispuesto": disposed}}


@pytest.mark.asyncio
async def test_card_with_missing_details_is_skipped():
    fetcher = UnicajaFetcher()
    fetcher._client = MagicMock()
    fetcher._client.list_accounts = AsyncMock(
        return_value={
            "cuentas": [
                {
                    "alias": "",
                    "descripcion": "CUENTA JOVEN",
                    "iban": IBAN,
                    "saldo": {"cantidad": 100.0, "moneda": "EUR"},
                    "disponible": {"cantidad": 100.0, "moneda": "EUR"},
                    "importeExcedido": {"cantidad": 0.0, "moneda": "EUR"},
                }
            ]
        }
    )
    fetcher._client.get_transfers_historic = AsyncMock(return_value={"noDatos": True})
    fetcher._client.get_cards = AsyncMock(
        return_value={"tarjetas": [_card("7021", "removed"), _card("1234", "active")]}
    )
    fetcher._client.get_card = AsyncMock(
        side_effect=lambda ppp, _: _card_details(
            {} if ppp == "removed" else {"cantidad": 10.0, "moneda": "EUR"}
        )
    )
    fetcher._client.get_loans = AsyncMock(return_value={"prestamos": []})

    position = await fetcher.global_position()

    cards = position.products[ProductType.CARD].entries
    assert [card.ending for card in cards] == ["1234"]
    assert cards[0].used == Dezimal("35")
