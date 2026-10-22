from domain.use_cases.get_local_models import GetLocalModels
from quart import jsonify, request


async def get_local_models(get_local_models_uc: GetLocalModels):
    refresh = request.args.get("refresh", "").lower() in ("1", "true")
    result = await get_local_models_uc.execute(refresh=refresh)
    return jsonify(result), 200
