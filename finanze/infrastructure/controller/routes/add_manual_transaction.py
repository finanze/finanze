from datetime import datetime

from dateutil.tz import tzlocal
from domain.use_cases.add_manual_transaction import AddManualTransaction
from quart import jsonify, request
from infrastructure.controller.mappers.transaction_mapper import (
    map_manual_transaction,
)


def _parse_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tzlocal())
    return dt


async def add_manual_transaction(add_manual_transaction_uc: AddManualTransaction):
    body = await request.get_json()

    try:
        tx = map_manual_transaction(body)
    except Exception as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        await add_manual_transaction_uc.execute(tx)
    except ValueError as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    return "", 204
