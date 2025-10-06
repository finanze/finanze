from uuid import UUID

from domain.use_cases.delete_manual_transaction import DeleteManualTransaction
from flask import jsonify


async def delete_manual_transaction(
    delete_manual_transaction_uc: DeleteManualTransaction, tx_id: str
):
    try:
        tx_uuid = UUID(tx_id)
    except (ValueError, TypeError):
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid transaction ID"}
        ), 400

    try:
        await delete_manual_transaction_uc.execute(tx_uuid)
    except ValueError as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    return "", 204
