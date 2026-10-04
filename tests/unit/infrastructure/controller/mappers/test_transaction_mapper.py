from uuid import UUID

import pytest

from domain.global_position import ProductType
from domain.transactions import (
    AccountTx,
    AddManualTransactionRequest,
    FundTx,
    TxType,
)
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


def test_map_fund_split_defaults_cash_fields_and_allows_null_shares():
    body = _fund_body(type="SPLIT", split_ratio="2")
    for field in ("amount", "shares", "price", "fees"):
        body.pop(field)

    request = map_add_manual_transaction(body)

    tx = request.txs[0]
    assert isinstance(tx, FundTx)
    assert tx.type == TxType.SPLIT
    assert tx.amount == 0
    assert tx.shares is None
    assert tx.price == 0
    assert tx.fees == 0
    assert str(tx.split_ratio) == "2"


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


def _account_body(**overrides):
    body = {
        "product_type": "ACCOUNT",
        "entity_id": ENTITY_ID,
        "date": "2025-03-01T12:00:00",
        "ref": "TX-ACC",
        "name": "Transfer",
        "amount": "100",
        "currency": "EUR",
        "type": "INFLOW",
    }
    body.update(overrides)
    return body


def test_map_account_iban_is_normalized():
    tx = map_add_manual_transaction(_account_body(iban=" es76 0000 0001 ")).txs[0]
    assert isinstance(tx, AccountTx)
    assert tx.iban == "ES7600000001"

    tx = map_add_manual_transaction(_account_body(iban="")).txs[0]
    assert tx.iban is None


def test_map_account_invalid_iban_raises():
    with pytest.raises(ValueError, match="Invalid IBAN"):
        map_add_manual_transaction(_account_body(iban="ES76-0001"))
