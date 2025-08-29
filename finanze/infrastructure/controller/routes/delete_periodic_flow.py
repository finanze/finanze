from uuid import UUID

from domain.use_cases.delete_periodic_flow import DeletePeriodicFlow
from flask import jsonify


def delete_periodic_flow(delete_periodic_flow_uc: DeletePeriodicFlow, flow_id: str):
    try:
        flow_uuid = UUID(flow_id)
    except ValueError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid UUID format"}
        ), 400

    delete_periodic_flow_uc.execute(flow_uuid)
    return "", 204
