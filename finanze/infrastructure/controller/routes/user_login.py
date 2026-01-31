from quart import jsonify, request

from domain.data_init import AlreadyUnlockedError, DecryptionError, MigrationAheadOfTime
from domain.exception.exceptions import (
    UserAlreadyLoggedIn,
    UserNotFound,
    InvalidUserCredentials,
)
from domain.use_cases.user_login import UserLogin
from domain.user_login import LoginRequest


async def user_login(user_login_uc: UserLogin):
    body = await request.get_json()
    username = body.get("username")
    password = body.get("password")
    if not username:
        return jsonify({"message": "Username not provided"}), 400
    if not password:
        return jsonify({"message": "Password not provided"}), 400

    login_request = LoginRequest(username=username, password=password)

    try:
        await user_login_uc.execute(login_request)
        return "", 204

    except DecryptionError as e:
        raise InvalidUserCredentials(str(e))

    except UserNotFound:
        return jsonify({"message": "Username not found"}), 404

    except UserAlreadyLoggedIn:
        return jsonify({"message": "User already logged in"}), 409

    except MigrationAheadOfTime as e:
        return jsonify({"message": str(e)}), 503

    except AlreadyUnlockedError:
        return "", 204
