from domain.external_integration import GoogleIntegrationCredentials
from domain.use_cases.connect_google import ConnectGoogle
from flask import jsonify, request


def connect_google(connect_google_uc: ConnectGoogle):
    body = request.json
    client_id = body.get("client_id")
    client_secret = body.get("client_secret")
    if not client_id or not client_secret:
        return jsonify({"message": "Error: missing client_id or client_secret"}), 400

    req = GoogleIntegrationCredentials(client_id, client_secret)
    connect_google_uc.execute(req)

    return "", 204
