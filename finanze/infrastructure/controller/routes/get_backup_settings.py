from quart import jsonify

from domain.use_cases.get_backup_settings import GetBackupSettings


async def get_backup_settings(get_backup_settings_uc: GetBackupSettings):
    settings = await get_backup_settings_uc.execute()

    response = {"mode": settings.mode.value}

    return jsonify(response), 200
