from uuid import UUID

from domain.exception.exceptions import RealEstateNotFound
from domain.real_estate import DeleteRealEstateRequest
from domain.use_cases.delete_real_estate import DeleteRealEstate
from flask import jsonify, request


async def delete_real_estate(
    delete_real_estate_uc: DeleteRealEstate, real_estate_id: str
):
    try:
        real_estate_id = UUID(real_estate_id)
    except (ValueError, TypeError):
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid real estate ID"}
        ), 400

    data = request.get_json() or {}
    remove_related_flows = data.get("remove_related_flows", False)

    delete_request = DeleteRealEstateRequest(
        id=real_estate_id, remove_related_flows=remove_related_flows
    )

    try:
        await delete_real_estate_uc.execute(delete_request)
    except RealEstateNotFound as e:
        return jsonify({"code": "NOT_FOUND", "message": str(e)}), 404

    return "", 204
