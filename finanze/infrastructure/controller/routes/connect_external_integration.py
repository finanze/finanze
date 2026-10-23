from urllib.parse import urlsplit

from domain.external_integration import (
    ConnectedExternalIntegrationRequest,
    ExternalIntegrationId,
)
from domain.use_cases.connect_external_integration import ConnectExternalIntegration
from quart import jsonify, request

INTEGRATION_COMPLETE_DEEPLINK = "finanze://integration/complete"


def _is_valid_completion_url(url: str) -> bool:
    if url.startswith(INTEGRATION_COMPLETE_DEEPLINK):
        return True
    parsed = urlsplit(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


async def connect_external_integration(
    connect_external_integrations_uc: ConnectExternalIntegration,
    integration_id: str,
):
    body = await request.get_json()

    try:
        external_integration_id = ExternalIntegrationId(integration_id)
    except ValueError:
        return (
            jsonify({"message": f"Error: invalid integration '{integration_id}'"}),
            400,
        )

    payload = (body or {}).get("payload")
    if not isinstance(payload, dict):
        return jsonify({"message": "Error: missing payload"}), 400

    completion_url = (body or {}).get("completion_url")
    if completion_url is not None and (
        not isinstance(completion_url, str)
        or not _is_valid_completion_url(completion_url)
    ):
        return jsonify({"message": "Error: invalid completion_url"}), 400

    req = ConnectedExternalIntegrationRequest(
        external_integration_id, payload, completion_url
    )
    result = await connect_external_integrations_uc.execute(req)

    if result.link:
        return jsonify(result), 200

    return "", 204
