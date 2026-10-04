from uuid import UUID

from domain.labeling import SaveLabelingRuleRequest
from domain.use_cases.update_labeling_rule import UpdateLabelingRule
from infrastructure.controller.mappers.labeling_mapper import map_rule
from quart import jsonify, request


async def update_labeling_rule(
    update_labeling_rule_uc: UpdateLabelingRule, rule_id: str
):
    body = await request.get_json()
    try:
        save_request = SaveLabelingRuleRequest(
            rule=map_rule(body, UUID(rule_id)),
            apply_to_existing=bool(body.get("apply_to_existing", False)),
        )
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    result = await update_labeling_rule_uc.execute(save_request)
    return jsonify(result), 200
