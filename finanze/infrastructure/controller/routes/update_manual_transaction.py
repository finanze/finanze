from uuid import UUID

from quart import jsonify, request

from domain.exception.exceptions import TransactionNotFound
from domain.use_cases.update_manual_transaction import UpdateManualTransaction
from infrastructure.controller.mappers.transaction_mapper import (
    map_manual_transaction,
)


async def update_manual_transaction(
    update_manual_transaction_uc: UpdateManualTransaction, tx_id: str
):
    try:
        tx_uuid = UUID(tx_id)
    except (ValueError, TypeError):
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid transaction ID"}
        ), 400

    body = await request.get_json()

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
