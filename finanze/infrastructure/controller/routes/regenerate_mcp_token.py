from dataclasses import asdict

from domain.use_cases.regenerate_mcp_token import RegenerateMcpToken
from quart import jsonify


async def regenerate_mcp_token(regenerate_mcp_token_uc: RegenerateMcpToken):
    config = await regenerate_mcp_token_uc.execute()
    return jsonify(asdict(config)), 200
