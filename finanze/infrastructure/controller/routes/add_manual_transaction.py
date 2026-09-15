from domain.use_cases.add_manual_transaction import AddManualTransaction
from quart import jsonify, request
from infrastructure.controller.mappers.transaction_mapper import (
    map_add_manual_transaction,
)


async def add_manual_transaction(add_manual_transaction_uc: AddManualTransaction):
    body = await request.get_json()

    try:
        add_request = map_add_manual_transaction(body)
    except Exception as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        await add_manual_transaction_uc.execute(add_request)
    except ValueError as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    return "", 204
