from quart import jsonify, request

from domain.crypto import AvailableCryptoAssetsRequest
from domain.use_cases.search_crypto_assets import SearchCryptoAssets


async def search_crypto_assets(search_crypto_assets_uc: SearchCryptoAssets):
    symbol = request.args.get("symbol") or None
    name = request.args.get("name") or None

    if not symbol and not name:
        return jsonify({"message": "Either symbol or name must be provided"}), 400

    if symbol and name:
        return jsonify(
            {"message": "Only one of symbol or name can be provided, not both"}
        ), 400

    query = symbol or name
    if len(query) < 1:
        return jsonify({"message": "Query must be at least 1 character long"}), 400

    raw_page = request.args.get("page", "1")
    raw_limit = request.args.get("limit", "50")

    try:
        page = int(raw_page)
        if page < 1:
            return jsonify({"message": "Page must be at least 1"}), 400
    except ValueError:
        return jsonify({"message": "Page must be a valid integer"}), 400

    try:
        limit = int(raw_limit)
        if limit < 1 or limit > 100:
            return jsonify({"message": "Limit must be between 1 and 100"}), 400
    except ValueError:
        return jsonify({"message": "Limit must be a valid integer"}), 400

    search_request = AvailableCryptoAssetsRequest(
        symbol=symbol,
        name=name,
        page=page,
        limit=limit,
    )

    result = await search_crypto_assets_uc.execute(search_request)
    return jsonify(result), 200
