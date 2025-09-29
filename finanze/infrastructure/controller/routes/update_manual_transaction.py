from datetime import datetime
from uuid import UUID

from dateutil.tz import tzlocal
from domain.exception.exceptions import TransactionNotFound
from domain.use_cases.update_manual_transaction import UpdateManualTransaction
from flask import jsonify, request
from infrastructure.controller.mappers.transaction_mapper import (
    map_manual_transaction,
)


def _parse_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tzlocal())
    return dt


async def update_manual_transaction(
    update_manual_transaction_uc: UpdateManualTransaction, tx_id: str
):
    try:
        tx_uuid = UUID(tx_id)
    except (ValueError, TypeError):
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid transaction ID"}
        ), 400

    body = request.json

    try:
        tx = map_manual_transaction(body, tx_id=tx_uuid)
    except Exception as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        await update_manual_transaction_uc.execute(tx)
    except TransactionNotFound:
        return jsonify({"code": "NOT_FOUND", "message": "Transaction not found"}), 404
    except Exception as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    return "", 204
