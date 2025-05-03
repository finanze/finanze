from flask import jsonify

from domain.use_cases.get_login_status import GetLoginStatus


def login_status(get_login_status_uc: GetLoginStatus):
    result = get_login_status_uc.execute()
    return jsonify({"status": result.status}), 200
