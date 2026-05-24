from quart import jsonify, request

from domain.data_init import AlreadyUnlockedError, DecryptionError
from domain.exception.exceptions import (
    InvalidPassword,
    InvalidUsername,
    UserAlreadyExists,
    InvalidUserCredentials,
)
from domain.use_cases.register_user import RegisterUser
from domain.user_login import LoginRequest


async def register_user(register_user_uc: RegisterUser):
    body = await request.get_json()
    username = body.get("username")
    password = body.get("password")
    guest = body.get("guest", False)

    if not username:
        return jsonify({"message": "Username not provided"}), 400
    if not guest and not password:
        return jsonify({"message": "Password not provided"}), 400

    login_request = LoginRequest(
        username=username,
        password=password,
        guest=guest,
    )

    try:
        await register_user_uc.execute(login_request)
        return "", 204

    except DecryptionError as e:
        raise InvalidUserCredentials(str(e))

    except InvalidUsername:
        return jsonify({"message": "Invalid username"}), 400

    except InvalidPassword:
        return jsonify({"message": "Invalid password"}), 400

    except UserAlreadyExists as e:
        return jsonify({"message": str(e)}), 409

    except AlreadyUnlockedError:
        return "", 204
