from uuid import UUID

import pytest

from domain.global_position import ProductType
from domain.transactions import AddManualTransactionRequest, FundTx, TxType
from infrastructure.controller.mappers.transaction_mapper import (
    map_add_manual_transaction,
)

ENTITY_ID = "e0000000-0000-0000-0000-000000000001"
HISTORIC_ID = "a0000000-0000-0000-0000-000000000010"


def _fund_body(**overrides):
    body = {
        "product_type": "FUND",
        "entity_id": ENTITY_ID,
        "date": "2025-03-01T12:00:00",
        "ref": "TX-FUND",
        "name": "Buy Fund",
        "amount": "5000.00",
        "currency": "EUR",
        "type": "BUY",
        "isin": "LU0000000001",
        "shares": "50",
        "price": "100",
        "fees": "10",
    }
    body.update(overrides)
    return body


def test_map_object_body():
    request = map_add_manual_transaction(_fund_body())
    assert isinstance(request, AddManualTransactionRequest)
    assert request.historic_entry_id is None
    assert len(request.txs) == 1
    tx = request.txs[0]
    assert isinstance(tx, FundTx)
    assert tx.product_type == ProductType.FUND
    assert tx.type == TxType.BUY
    assert str(tx.entity.id) == ENTITY_ID


def test_map_object_body_with_historic_entry_id():
    request = map_add_manual_transaction(_fund_body(historic_entry_id=HISTORIC_ID))
    assert request.historic_entry_id == UUID(HISTORIC_ID)
    assert len(request.txs) == 1


def test_map_list_body():
    request = map_add_manual_transaction(
        [
            _fund_body(ref="TX-OUT", name="Origin", type="TRANSFER_OUT"),
            _fund_body(ref="TX-IN", name="Dest", type="TRANSFER_IN"),
        ]
    )
    assert request.historic_entry_id is None
    assert len(request.txs) == 2
    assert request.txs[0].type == TxType.TRANSFER_OUT
    assert request.txs[0].name == "Origin"
    assert request.txs[1].type == TxType.TRANSFER_IN
    assert request.txs[1].name == "Dest"


def test_map_list_uses_first_historic_entry_id():
    request = map_add_manual_transaction(
        [
            _fund_body(ref="TX-OUT", type="TRANSFER_OUT"),
            _fund_body(
                ref="TX-IN",
                type="TRANSFER_IN",
                historic_entry_id=HISTORIC_ID,
            ),
        ]
    )
    assert request.historic_entry_id == UUID(HISTORIC_ID)


def test_map_empty_list_raises():
    with pytest.raises(ValueError, match="At least one transaction is required"):
        map_add_manual_transaction([])


def test_map_invalid_body_raises():
    with pytest.raises(ValueError, match="Body must be a JSON object or array"):
        map_add_manual_transaction("invalid")
