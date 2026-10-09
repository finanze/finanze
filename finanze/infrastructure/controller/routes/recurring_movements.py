from uuid import UUID

from domain.cashflow import DEFAULT_RECURRING_LOOKBACK_MONTHS, RecurringMovementsQuery
from domain.transactions import ACCOUNT_MOVEMENT_TYPES, TxType
from domain.use_cases.get_recurring_movements import GetRecurringMovements
from quart import jsonify, request


async def recurring_movements(get_recurring_movements_uc: GetRecurringMovements):
    currency = (request.args.get("currency") or "").strip().upper()
    if not currency:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "currency is required."}
        ), 400

    try:
        lookback_months = int(
            request.args.get("lookback_months", DEFAULT_RECURRING_LOOKBACK_MONTHS)
        )
        entities = [UUID(e) for e in request.args.getlist("entity")] or None
        raw_type = request.args.get("type")
        tx_type = TxType(raw_type.upper()) if raw_type else None
        if tx_type is not None and tx_type not in ACCOUNT_MOVEMENT_TYPES:
            raise ValueError(f"Unsupported type {tx_type.value}")
    except ValueError as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    result = await get_recurring_movements_uc.execute(
        RecurringMovementsQuery(
            currency=currency,
            lookback_months=lookback_months,
            entities=entities,
            type=tx_type,
        )
    )
    return jsonify(result), 200
