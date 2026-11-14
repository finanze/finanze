from domain.ai import AITask
from domain.use_cases.get_ai_providers import GetAIProviders
from quart import jsonify, request


async def get_ai_providers(get_ai_providers_uc: GetAIProviders):
    task = request.args.get("task")
    try:
        parsed_task = AITask(task) if task else None
    except ValueError:
        return jsonify({"code": "INVALID_REQUEST", "message": "Invalid task"}), 400
    result = await get_ai_providers_uc.execute(parsed_task)
    return jsonify(result), 200
