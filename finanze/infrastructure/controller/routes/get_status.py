from quart import jsonify

from domain.use_cases.get_status import GetStatus


async def status(get_status_uc: GetStatus):
    result = await get_status_uc.execute()

    user = None
    if result.user:
        user = {
            "id": result.user.hashed_id(),
            "username": result.user.username,
            "path": str(result.user.path.absolute()),
        }

    response = {
        "status": result.status.value,
        "server": {
            "version": result.server.version,
            "platform_type": result.server.platform_type,
            "options": {
                "dataDir": result.server.options.data_dir,
                "port": result.server.options.port,
                "logLevel": result.server.options.log_level.value
                if result.server.options.log_level
                else None,
                "logDir": result.server.options.log_dir,
                "logFileLevel": result.server.options.log_file_level.value
                if result.server.options.log_file_level
                else None,
                "thirdPartyLogLevel": result.server.options.third_party_log_level.value
                if result.server.options.third_party_log_level
                else None,
            },
        },
        "features": result.features,
        "user": user,
        "lastLogged": result.last_logged,
    }

    return jsonify(response), 200
