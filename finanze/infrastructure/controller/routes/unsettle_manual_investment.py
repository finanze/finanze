from uuid import UUID

from domain.exception.exceptions import (
    ManualHistoricEntryNotFinal,
    ManualHistoricEntryNotFound,
    ManualInvestmentNotFound,
)
from domain.historic import UnsettleManualInvestmentRequest
from domain.use_cases.unsettle_manual_investment import UnsettleManualInvestment
from quart import jsonify


async def unsettle_manual_investment(
    unsettle_uc: UnsettleManualInvestment, entry_id: str
):
    try:
        req = UnsettleManualInvestmentRequest(entry_id=UUID(entry_id))
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        await unsettle_uc.execute(req)
    except (ManualHistoricEntryNotFound, ManualInvestmentNotFound) as e:
        return jsonify({"code": "NOT_FOUND", "message": str(e)}), 404
    except ManualHistoricEntryNotFinal as e:
        return jsonify({"code": "INVALID_STATE", "message": str(e)}), 409

    return "", 204
