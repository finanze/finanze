from domain.use_cases.get_status import GetStatus
from flask import jsonify


def status(get_status_uc: GetStatus):
    result = get_status_uc.execute()

    response = {
        "status": result.status.value,
        "server": {
            "version": result.server.version,
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
        "user": result.user,
        "lastLogged": result.last_logged,
    }

    return jsonify(response), 200
