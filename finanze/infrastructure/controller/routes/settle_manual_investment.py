from datetime import datetime
from uuid import UUID

from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.exception.exceptions import EntityNotFound, ManualInvestmentNotFound
from domain.global_position import ProductType
from domain.historic import SettleManualInvestmentRequest
from domain.use_cases.settle_manual_investment import SettleManualInvestment
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


async def settle_manual_investment(settle_uc: SettleManualInvestment):
    body = await request.get_json()

    try:
        req = SettleManualInvestmentRequest(
            entity_id=UUID(body["entity_id"]),
            entry_id=UUID(body["entry_id"]),
            product_type=ProductType(body["product_type"]),
            maturity=_parse_datetime(body.get("maturity")),
            interests=_dez(body.get("interests")),
            fees=_dez(body.get("fees")) or Dezimal(0),
            retentions=_dez(body.get("retentions")) or Dezimal(0),
            pending_capital=_dez(body.get("pending_capital")) or Dezimal(0),
            create_investment_tx=bool(body.get("create_investment_tx", False)),
        )
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        await settle_uc.execute(req)
    except (EntityNotFound, ManualInvestmentNotFound) as e:
        return jsonify({"code": "NOT_FOUND", "message": str(e)}), 404

    return "", 204
