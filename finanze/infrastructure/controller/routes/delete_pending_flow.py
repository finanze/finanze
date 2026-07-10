from uuid import UUID

from domain.use_cases.delete_pending_flow import DeletePendingFlow
from quart import jsonify


async def delete_pending_flow(delete_pending_flow_uc: DeletePendingFlow, flow_id: str):
    try:
        flow_uuid = UUID(flow_id)
    except ValueError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid UUID format"}
        ), 400

    await delete_pending_flow_uc.execute(flow_uuid)
    return "", 204
