from flask import request
from pydantic import ValidationError

from domain.settings import Settings
from domain.use_cases.update_settings import UpdateSettings


def update_settings(update_settings_uc: UpdateSettings):
    new_config = request.get_json()
    try:
        parsed_settings = Settings(**new_config)
    except ValidationError:
        return "", 400

    update_settings_uc.execute(parsed_settings)
    return "", 204
