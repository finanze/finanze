from flask import jsonify

from domain.use_cases.get_settings import GetSettings


def get_settings(get_settings_uc: GetSettings):
    config_data = get_settings_uc.execute()
    return jsonify(config_data), 200
