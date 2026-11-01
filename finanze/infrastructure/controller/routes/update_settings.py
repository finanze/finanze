from domain.settings import PartialSettings, SettingsSection
from domain.use_cases.update_settings import UpdateSettings
from quart import jsonify, request
from pydantic import ValidationError

SECTION_KEYS = {section.value for section in SettingsSection}
IGNORED_KEYS = {"lastUpdate", "version"}


def _invalid(message: str):
    return jsonify({"code": "INVALID_SETTINGS", "message": message}), 400


async def update_settings(update_settings_uc: UpdateSettings):
    body = await request.get_json()
    if not isinstance(body, dict):
        return _invalid("Settings body must be an object")

    unknown = set(body) - SECTION_KEYS - IGNORED_KEYS
    if unknown:
        return _invalid(f"Unknown settings sections: {', '.join(sorted(unknown))}")

    try:
        parsed_settings = PartialSettings(
            **{key: value for key, value in body.items() if key in SECTION_KEYS}
        )
    except ValidationError as e:
        return _invalid(str(e))

    if not parsed_settings.included_sections():
        return _invalid("No settings sections provided")

    await update_settings_uc.execute(parsed_settings)
    return "", 204
