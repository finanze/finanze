from flask import jsonify

from domain.use_cases.get_cloud_auth import GetCloudAuth


def get_cloud_auth(get_cloud_auth_uc: GetCloudAuth):
    result = get_cloud_auth_uc.execute()

    if result is None:
        return "", 204

    return jsonify(
        {
            "email": result.email,
            "role": result.role.value,
            "permissions": result.permissions,
            "token": {
                "access_token": result.token.access_token,
                "refresh_token": result.token.refresh_token,
                "token_type": result.token.token_type,
                "expires_at": result.token.expires_at,
            },
        }
    ), 200
