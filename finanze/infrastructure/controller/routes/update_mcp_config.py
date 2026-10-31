from dataclasses import asdict

from domain.mcp import UpdateMcpConfigRequest
from domain.use_cases.update_mcp_config import UpdateMcpConfig
from pydantic import ValidationError
from quart import jsonify, request


async def update_mcp_config(update_mcp_config_uc: UpdateMcpConfig):
    body = await request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid request body."}
        ), 400

    enabled = body.get("enabled")
    read_only = body.get("read_only")
    if not isinstance(enabled, bool) or not isinstance(read_only, bool):
        return jsonify(
            {
                "code": "INVALID_REQUEST",
                "message": "enabled and read_only must be booleans.",
            }
        ), 400

    try:
        update = UpdateMcpConfigRequest(
            enabled=enabled,
            read_only=read_only,
            category_access=body.get("category_access"),
        )
    except ValidationError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid tool category preferences."}
        ), 400

    config = await update_mcp_config_uc.execute(update)
    return jsonify(asdict(config)), 200
