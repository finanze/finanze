from dataclasses import asdict

from domain.use_cases.get_mcp_config import GetMcpConfig
from quart import jsonify


async def get_mcp_config(get_mcp_config_uc: GetMcpConfig):
    config = await get_mcp_config_uc.execute()
    return jsonify(asdict(config)), 200
