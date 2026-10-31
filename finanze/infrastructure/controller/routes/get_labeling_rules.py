from domain.use_cases.get_labeling_rules import GetLabelingRules
from quart import jsonify


async def get_labeling_rules(get_labeling_rules_uc: GetLabelingRules):
    result = await get_labeling_rules_uc.execute()
    return jsonify(result), 200
