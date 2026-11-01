from domain.use_cases.get_labels import GetLabels
from quart import jsonify


async def get_labels(get_labels_uc: GetLabels):
    result = await get_labels_uc.execute()
    return jsonify(result), 200
