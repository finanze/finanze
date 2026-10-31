from uuid import UUID

from domain.use_cases.delete_label import DeleteLabel
from quart import jsonify


async def delete_label(delete_label_uc: DeleteLabel, label_id: str):
    try:
        label_uuid = UUID(label_id)
    except ValueError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid UUID format"}
        ), 400

    await delete_label_uc.execute(label_uuid)
    return "", 204
