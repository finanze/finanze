from domain.external_integration import (
    GoCardlessIntegrationCredentials,
)
from domain.use_cases.connect_gocardless import ConnectGoCardless
from flask import jsonify, request


def connect_gocardless(connect_gocardless_uc: ConnectGoCardless):
    body = request.json
    secret_key = body.get("secret_key")
    if not secret_key:
        return jsonify({"message": "Error: missing secret_key"}), 400
    secret_id = body.get("secret_id")
    if not secret_id:
        return jsonify({"message": "Error: missing secret_id"}), 400

    req = GoCardlessIntegrationCredentials(secret_id=secret_id, secret_key=secret_key)
    connect_gocardless_uc.execute(req)

    return "", 204
