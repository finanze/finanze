from domain.external_integration import (
    EtherscanIntegrationData,
)
from domain.use_cases.connect_etherscan import ConnectEtherscan
from flask import jsonify, request


def connect_etherscan(connect_etherscan_uc: ConnectEtherscan):
    body = request.json
    api_key = body.get("api_key")
    if not api_key:
        return jsonify({"message": "Error: missing api_key"}), 400

    req = EtherscanIntegrationData(api_key)
    connect_etherscan_uc.execute(req)

    return "", 204
