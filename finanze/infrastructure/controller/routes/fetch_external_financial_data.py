from uuid import UUID

from domain.entity import Feature
from domain.external_entity import ExternalFetchRequest
from domain.use_cases.fetch_external_financial_data import FetchExternalFinancialData
from quart import jsonify, request


async def fetch_external_financial_data(
    fetch_external_financial_data_uc: FetchExternalFinancialData,
    external_entity_id: str,
):
    try:
        external_entity_id = UUID(external_entity_id)
    except ValueError:
        return jsonify({"message": "Invalid external entity ID"}), 400

    body = await request.get_json(silent=True)
    if body is None:
        if getattr(request, "content_length", 0) or (
            hasattr(request, "get_data") and await request.get_data()
        ):
            return jsonify({"message": "Invalid external fetch body"}), 400
        body = {}
    if not isinstance(body, dict) or set(body) - {"features", "deep"}:
        return jsonify({"message": "Invalid external fetch body"}), 400
    deep = body.get("deep", False)
    if not isinstance(deep, bool):
        return jsonify({"message": "Invalid deep option"}), 400
    features = None
    if "features" in body:
        values = body["features"]
        if (
            not isinstance(values, list)
            or not values
            or any(value not in ("POSITION", "TRANSACTIONS") for value in values)
        ):
            return jsonify({"message": "Invalid external fetch features"}), 400
        features = list(dict.fromkeys(Feature(value) for value in values))

    fetch_request = ExternalFetchRequest(
        external_entity_id=external_entity_id,
        features=features,
        deep=deep,
    )
    result = await fetch_external_financial_data_uc.execute(fetch_request)

    response = {"code": result.code}
    if result.details:
        response["details"] = result.details

    return jsonify(response), 200
