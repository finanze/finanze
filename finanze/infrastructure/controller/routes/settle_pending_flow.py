from uuid import UUID

from domain.earnings_expenses import SettlePendingFlowRequest
from domain.exception.exceptions import FlowNotFound, ManualAccountNotFound
from domain.use_cases.settle_pending_flow import SettlePendingFlow
from quart import jsonify, request


async def settle_pending_flow(settle_pending_flow_uc: SettlePendingFlow):
    body = await request.get_json()

    try:
        settle_request = SettlePendingFlowRequest(
            flow_id=UUID(body["flow_id"]),
            account_id=UUID(body["account_id"]),
        )
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        await settle_pending_flow_uc.execute(settle_request)
    except FlowNotFound:
        return jsonify({"code": "NOT_FOUND", "message": "Flow not found"}), 404
    except ManualAccountNotFound:
        return jsonify({"code": "NOT_FOUND", "message": "Account not found"}), 404
    except ValueError as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    return "", 204
