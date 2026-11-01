from domain.use_cases.get_external_labeling_models import GetExternalLabelingModels
from quart import jsonify


async def get_external_labeling_models(
    get_external_labeling_models_uc: GetExternalLabelingModels, provider_id: str
):
    result = await get_external_labeling_models_uc.execute(provider_id)
    return jsonify(result), 200
