from uuid import UUID

from domain.use_cases.restore_recurring_movement import RestoreRecurringMovement
from quart import jsonify


async def restore_recurring_movement(
    restore_recurring_movement_uc: RestoreRecurringMovement, ignored_id: str
):
    try:
        ignored_uuid = UUID(ignored_id)
    except ValueError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid UUID format"}
        ), 400

    await restore_recurring_movement_uc.execute(ignored_uuid)
    return "", 204
