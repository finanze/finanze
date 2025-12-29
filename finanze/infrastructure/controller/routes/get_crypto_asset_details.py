from flask import jsonify, request

from domain.external_integration import ExternalIntegrationId
from domain.use_cases.get_crypto_asset_details import GetCryptoAssetDetails


def get_crypto_asset_details(
    get_crypto_asset_details_uc: GetCryptoAssetDetails, asset_id: str
):
    provider_param = request.args.get("provider")

    if not provider_param:
        return jsonify({"message": "Provider query parameter is required"}), 400

    try:
        provider = ExternalIntegrationId(provider_param)
    except ValueError:
        return jsonify({"message": f"Invalid provider: {provider_param}"}), 400

    if not asset_id or len(asset_id.strip()) < 1:
        return jsonify({"message": "Asset ID is required"}), 400

    result = get_crypto_asset_details_uc.execute(
        provider_id=asset_id.strip(),
        provider=provider,
    )

    return jsonify(result), 200
