from domain.use_cases.get_ai_server_info import GetAIServerInfo
from quart import jsonify


async def get_ai_server_info(get_ai_server_info_uc: GetAIServerInfo, provider_id: str):
    result = await get_ai_server_info_uc.execute(provider_id)
    return jsonify(result), 200
