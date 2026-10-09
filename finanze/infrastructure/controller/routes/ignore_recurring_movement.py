from domain.cashflow import IgnoredRecurringMovement
from domain.dezimal import Dezimal
from domain.transactions import ACCOUNT_MOVEMENT_TYPES, TxType
from domain.use_cases.ignore_recurring_movement import IgnoreRecurringMovement
from quart import jsonify, request


async def ignore_recurring_movement(
    ignore_recurring_movement_uc: IgnoreRecurringMovement,
):
    body = await request.get_json()
    try:
        key = (body.get("key") or "").strip()
        currency = (body.get("currency") or "").strip().upper()
        tx_type = TxType(body["type"])
        amount = Dezimal(body["amount"])
        if not key or not currency:
            raise ValueError("key and currency are required.")
        if tx_type not in ACCOUNT_MOVEMENT_TYPES:
            raise ValueError(f"Unsupported type {tx_type.value}")
        if amount <= 0:
            raise ValueError("amount must be positive.")
    except (KeyError, ValueError, TypeError, AttributeError, ArithmeticError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    result = await ignore_recurring_movement_uc.execute(
        IgnoredRecurringMovement(
            key=key, type=tx_type, currency=currency, amount=amount
        )
    )
    return jsonify(result), 201
