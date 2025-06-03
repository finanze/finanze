from flask import request, jsonify
from werkzeug.exceptions import InternalServerError, Unauthorized

from domain.data_init import DecryptionError, AlreadyUnlockedError
from domain.use_cases.user_login import UserLogin
from domain.user_login import LoginRequest


def user_login(user_login_uc: UserLogin):
    body = request.json
    password = body.get("password")
    if not password:
        return jsonify({"message": "Password not provided"}), 400

    login_request = LoginRequest(password=password)

    try:
        user_login_uc.execute(login_request)
        return "", 204

    except DecryptionError as e:
        raise Unauthorized(str(e))

    except AlreadyUnlockedError:
        return "", 204

    except Exception:
        raise InternalServerError("An internal error occurred during unlock.")
