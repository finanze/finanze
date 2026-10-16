from domain.labeling import LabelingRulePreviewRequest
from domain.use_cases.preview_labeling_rule import PreviewLabelingRule
from infrastructure.controller.mappers.labeling_mapper import map_conditions
from quart import jsonify, request


async def preview_labeling_rule(preview_labeling_rule_uc: PreviewLabelingRule):
    body = await request.get_json()
    try:
        preview_request = LabelingRulePreviewRequest(
            conditions=map_conditions(body.get("conditions") or {}),
            limit=int(body.get("limit", 10)),
        )
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    result = await preview_labeling_rule_uc.execute(preview_request)
    return jsonify(result), 200
