from datetime import date
from uuid import UUID

from domain.cashflow import CashflowGranularity, CashflowQuery
from domain.use_cases.get_cashflow_summary import GetCashflowSummary
from quart import jsonify, request

MAX_CASHFLOW_RANGE_DAYS = 3660


async def cashflow_summary(get_cashflow_summary_uc: GetCashflowSummary):
    currency = (request.args.get("currency") or "").strip().upper()
    if not currency:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "currency is required."}
        ), 400

    try:
        from_date = date.fromisoformat(request.args["from_date"])
        to_date = date.fromisoformat(request.args["to_date"])
        entities = [UUID(e) for e in request.args.getlist("entity")] or None
        granularity = CashflowGranularity(
            request.args.get("granularity", CashflowGranularity.MONTH.value).upper()
        )
    except (KeyError, ValueError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    if from_date > to_date:
        return jsonify(
            {
                "code": "INVALID_REQUEST",
                "message": "from_date must be before or equal to to_date",
            }
        ), 400
    if (to_date - from_date).days > MAX_CASHFLOW_RANGE_DAYS:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Date range is too large"}
        ), 400

    result = await get_cashflow_summary_uc.execute(
        CashflowQuery(
            currency=currency,
            from_date=from_date,
            to_date=to_date,
            entities=entities,
            granularity=granularity,
        )
    )
    return jsonify(result), 200
