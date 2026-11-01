from dataclasses import asdict

from domain.use_cases.get_mcp_config import GetMcpConfig
from quart import jsonify

from infrastructure.mcp.tool_catalog import McpToolCatalog


async def get_mcp_config(get_mcp_config_uc: GetMcpConfig, catalog: McpToolCatalog):
    config = await get_mcp_config_uc.execute()
    return jsonify({**asdict(config), **catalog.metadata()}), 200
