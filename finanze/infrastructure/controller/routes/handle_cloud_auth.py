from quart import request, jsonify

from domain.cloud_auth import CloudAuthRequest, CloudAuthToken
from domain.use_cases.handle_cloud_auth import HandleCloudAuth


async def handle_cloud_auth(handle_cloud_auth_uc: HandleCloudAuth):
    body = await request.get_json()

    token = None
    token_data = body.get("token")
    if token_data:
        token = CloudAuthToken(
            access_token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type"),
            expires_at=token_data.get("expires_at"),
        )

    auth_request = CloudAuthRequest(
        token=token,
    )

    result = await handle_cloud_auth_uc.execute(auth_request)

    return jsonify(
        {
            "role": result.role.value if result.role else None,
            "permissions": result.permissions,
        }
    ), 200
