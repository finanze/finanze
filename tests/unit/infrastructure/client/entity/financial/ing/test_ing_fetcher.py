from domain.dezimal import Dezimal
from domain.transactions import TxType
from infrastructure.client.entity.financial.ing.ing_fetcher import (
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
