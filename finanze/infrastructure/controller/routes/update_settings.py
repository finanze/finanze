from domain.settings import Settings
from domain.use_cases.update_settings import UpdateSettings
from quart import jsonify, request
from pydantic import ValidationError


async def update_settings(update_settings_uc: UpdateSettings):
    new_config = await request.get_json()
    try:
        parsed_settings = Settings(**new_config)
    except ValidationError as e:
        return jsonify({"code": "INVALID_SETTINGS", "message": str(e)}), 400

    await update_settings_uc.execute(parsed_settings)
    return "", 204
