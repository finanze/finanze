from flask import jsonify

from domain.use_cases.get_status import GetStatus


def status(get_status_uc: GetStatus):
    result = get_status_uc.execute()

    response = {
        "status": result.status.value,
        "server": {
            "dataDir": result.server.data_dir,
            "port": result.server.port,
            "logLevel": result.server.log_level.value
            if result.server.log_level
            else None,
            "logDir": result.server.log_dir,
            "logFileLevel": result.server.log_file_level.value
            if result.server.log_file_level
            else None,
            "thirdPartyLogLevel": result.server.third_party_log_level.value
            if result.server.third_party_log_level
            else None,
        },
        "user": result.user,
        "lastLogged": result.last_logged,
    }

    return jsonify(response), 200
