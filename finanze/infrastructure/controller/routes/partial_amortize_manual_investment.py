from datetime import datetime
from uuid import UUID

from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.exception.exceptions import EntityNotFound, ManualInvestmentNotFound
from domain.global_position import ProductType
from domain.historic import PartialAmortizeManualInvestmentRequest
from domain.use_cases.partial_amortize_manual_investment import (
    PartialAmortizeManualInvestment,
)
from quart import jsonify, request


def _parse_datetime(value):
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tzlocal())
    return dt


def _dez(value):
    if value is None:
        return None
    return Dezimal(str(value))


async def partial_amortize_manual_investment(
    partial_amortize_uc: PartialAmortizeManualInvestment,
):
    body = await request.get_json()

    try:
        req = PartialAmortizeManualInvestmentRequest(
            entity_id=UUID(body["entity_id"]),
            entry_id=UUID(body["entry_id"]),
            product_type=ProductType(body["product_type"]),
            amount=_dez(body["amount"]),
            date=_parse_datetime(body.get("date")),
            interests=_dez(body.get("interests")) or Dezimal(0),
            fees=_dez(body.get("fees")) or Dezimal(0),
            retentions=_dez(body.get("retentions")) or Dezimal(0),
            create_investment_tx=bool(body.get("create_investment_tx", False)),
        )
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        await partial_amortize_uc.execute(req)
    except (EntityNotFound, ManualInvestmentNotFound) as e:
        return jsonify({"code": "NOT_FOUND", "message": str(e)}), 404

    return "", 204
