from uuid import UUID

from domain.entity import Feature
from domain.entity_login import LoginOptions, TwoFactor
from domain.fetch_result import FetchOptions, FetchRequest
from domain.use_cases.fetch_financial_data import FetchFinancialData
from quart import jsonify, request


def _map_features(features: list[str]) -> list[Feature]:
    return [Feature[feature] for feature in features]


async def fetch_financial_data(fetch_financial_data_uc: FetchFinancialData):
    body = await request.get_json()

    entity_account_id = body.get("entityAccountId", None)
    if not entity_account_id:
        return jsonify({"message": "Entity account not provided"}), 400

    entity_account_id = UUID(entity_account_id)

    feature_fields = body.get("features", [])
    try:
        features = _map_features(feature_fields)
    except KeyError as e:
        return jsonify({"message": f"Invalid feature {e}"}), 400

    code = body.get("code", None)
    process_id = body.get("processId", None)
    token = body.get("token", None)
    avoid_new_login = body.get("avoidNewLogin", False)
    deep = body.get("deep", False)
    credentials = body.get("credentials", None)
    # if not process_id:
    #    return '{"code": "CODE_REQUESTED", "processId": "aaaa"}'
    # else:
    # return '{"code": "MANUAL_LOGIN"}'
    fetch_request = FetchRequest(
        entity_account_id=entity_account_id,
        features=features,
        two_factor=TwoFactor(code=code, process_id=process_id, token=token),
        fetch_options=FetchOptions(deep=deep),
        login_options=LoginOptions(avoid_new_login=avoid_new_login),
        credentials=credentials,
    )
    result = await fetch_financial_data_uc.execute(fetch_request)

    response = {"code": result.code}
    if result.details:
        response["details"] = result.details
    if result.data:
        response["data"] = result.data
    if result.confirmation_type:
        response["confirmationType"] = result.confirmation_type

    return jsonify(response), 200
