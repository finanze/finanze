from uuid import UUID

from domain.entity import Feature
from domain.entity_login import LoginOptions, TwoFactor
from domain.fetch_result import FetchOptions, FetchRequest
from domain.use_cases.fetch_financial_data import FetchFinancialData
from flask import jsonify, request


def _map_features(features: list[str]) -> list[Feature]:
    return [Feature[feature] for feature in features]


async def fetch_financial_data(fetch_financial_data_uc: FetchFinancialData):
    body = request.json

    entity = body.get("entity", None)
    if not entity:
        return jsonify({"message": "Source entity not provided"}), 400

    entity = UUID(entity)

    feature_fields = body.get("features", [])
    try:
        features = _map_features(feature_fields)
    except KeyError as e:
        return jsonify({"message": f"Invalid feature {e}"}), 400

    code = body.get("code", None)
    process_id = body.get("processId", None)
    avoid_new_login = body.get("avoidNewLogin", False)
    deep = body.get("deep", False)

    fetch_request = FetchRequest(
        entity_id=entity,
        features=features,
        two_factor=TwoFactor(code=code, process_id=process_id),
        fetch_options=FetchOptions(deep=deep),
        login_options=LoginOptions(avoid_new_login=avoid_new_login),
    )
    result = await fetch_financial_data_uc.execute(fetch_request)

    response = {"code": result.code}
    if result.details:
        response["details"] = result.details
    if result.data:
        response["data"] = result.data

    return jsonify(response), 200
