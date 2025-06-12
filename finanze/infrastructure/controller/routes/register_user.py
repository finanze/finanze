from domain.data_init import AlreadyUnlockedError, DecryptionError
from domain.exception.exceptions import UserAlreadyExists
from domain.use_cases.register_user import RegisterUser
from domain.user_login import LoginRequest
from flask import jsonify, request
from werkzeug.exceptions import Unauthorized


def register_user(register_user_uc: RegisterUser):
    body = request.json
    username = body.get("username")
    password = body.get("password")
    if not username:
        return jsonify({"message": "Username not provided"}), 400
    if not password:
        return jsonify({"message": "Password not provided"}), 400

    login_request = LoginRequest(username=username, password=password)

    try:
        register_user_uc.execute(login_request)
        return "", 204

    except DecryptionError as e:
        raise Unauthorized(str(e))

    except UserAlreadyExists as e:
        return jsonify({"message": str(e)}), 409

    except AlreadyUnlockedError:
        return "", 204
