from flask import jsonify, request

from domain.backup import BackupSettings, BackupMode
from domain.use_cases.save_backup_settings import SaveBackupSettings


def save_backup_settings(save_backup_settings_uc: SaveBackupSettings):
    body = request.json
    mode_str = body.get("mode")

    if not mode_str:
        return {"message": "Field 'mode' is required"}, 400

    try:
        mode = BackupMode(mode_str)
    except ValueError:
        return {"message": "Invalid mode value. Must be one of: OFF, MANUAL, AUTO"}, 400

    settings = BackupSettings(mode=mode)
    result = save_backup_settings_uc.execute(settings)

    response = {"mode": result.mode.value}

    return jsonify(response), 200
