from dataclasses import asdict

from quart import jsonify, request

from domain.settings import SettingsSection
from domain.use_cases.get_settings import GetSettings


async def get_settings(get_settings_uc: GetSettings):
    try:
        sections = {SettingsSection(key) for key in request.args.getlist("key")}
    except ValueError as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    settings = await get_settings_uc.execute(sections or None)
    return jsonify(
        {key: value for key, value in asdict(settings).items() if value is not None}
    ), 200
