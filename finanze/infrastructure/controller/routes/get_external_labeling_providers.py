from domain.use_cases.get_external_labeling_providers import (
    GetExternalLabelingProviders,
)
from quart import jsonify


async def get_external_labeling_providers(
    get_external_labeling_providers_uc: GetExternalLabelingProviders,
):
    result = await get_external_labeling_providers_uc.execute()
    return jsonify(result), 200
