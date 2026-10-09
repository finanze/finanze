from uuid import UUID

from domain.use_cases.delete_labeling_rule import DeleteLabelingRule
from quart import jsonify


async def delete_labeling_rule(
    delete_labeling_rule_uc: DeleteLabelingRule, rule_id: str
):
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid UUID format"}
        ), 400

    await delete_labeling_rule_uc.execute(rule_uuid)
    return "", 204
