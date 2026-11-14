from domain.ai import AITask
from domain.use_cases.get_ai_models import GetAIModels
from quart import jsonify, request


async def get_ai_models(get_ai_models_uc: GetAIModels, provider_id: str):
    task = request.args.get("task")
    try:
        parsed_task = AITask(task) if task else None
    except ValueError:
        return jsonify({"code": "INVALID_REQUEST", "message": "Invalid task"}), 400
    result = await get_ai_models_uc.execute(provider_id, parsed_task)
    return jsonify(result), 200
