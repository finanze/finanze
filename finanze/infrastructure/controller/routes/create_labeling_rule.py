from domain.labeling import SaveLabelingRuleRequest
from domain.use_cases.create_labeling_rule import CreateLabelingRule
from infrastructure.controller.mappers.labeling_mapper import map_rule
from quart import jsonify, request


async def create_labeling_rule(create_labeling_rule_uc: CreateLabelingRule):
    body = await request.get_json()
    try:
        save_request = SaveLabelingRuleRequest(
            rule=map_rule(body),
            apply_to_existing=bool(body.get("apply_to_existing", False)),
        )
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    result = await create_labeling_rule_uc.execute(save_request)
    return jsonify(result), 201
