from uuid import UUID

from flask import request, jsonify

from domain.financial_entity import Feature
from domain.entity_login import TwoFactor, LoginOptions
from domain.scrap_result import ScrapRequest
from domain.use_cases.scrape import Scrape


def _map_features(features: list[str]) -> list[Feature]:
    return [Feature[feature] for feature in features]


async def scrape(scrape: Scrape):
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

    scrape_request = ScrapRequest(
        entity_id=entity,
        features=features,
        two_factor=TwoFactor(code=code, process_id=process_id),
        options=LoginOptions(avoid_new_login=avoid_new_login),
    )
    result = await scrape.execute(scrape_request)

    response = {"code": result.code}
    if result.details:
        response["details"] = result.details
    if result.data:
        response["data"] = result.data

    return jsonify(response), 200
