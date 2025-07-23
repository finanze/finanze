from domain.data_init import DecryptionError
from domain.exception.exceptions import UserAlreadyLoggedIn, UserNotFound
from domain.use_cases.change_user_password import ChangeUserPassword
from domain.user_login import ChangePasswordRequest
from flask import jsonify, request
from werkzeug.exceptions import Unauthorized


def change_user_password(change_user_password_uc: ChangeUserPassword):
    body = request.json
    username = body.get("username")
    old_password = body.get("oldPassword")
    new_password = body.get("newPassword")
    if not username:
        return jsonify({"message": "Username not provided"}), 400
    if not old_password:
        return jsonify({"message": "Old password not provided"}), 400
    if not new_password:
        return jsonify({"message": "New password not provided"}), 400

    change_password_request = ChangePasswordRequest(
        username=username, old_password=old_password, new_password=new_password
    )

    try:
        change_user_password_uc.execute(change_password_request)
        return "", 204

    except DecryptionError as e:
        raise Unauthorized(str(e))

    except UserNotFound:
        return jsonify({"message": "Username not found"}), 404

    except UserAlreadyLoggedIn as e:
        return jsonify({"message": str(e)}), 400

    except ValueError as e:
        return jsonify({"message": str(e)}), 400
