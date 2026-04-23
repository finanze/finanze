from domain.external_entity import ExternalEntityCandidatesQuery
from domain.use_cases.get_available_external_entities import (
    GetAvailableExternalEntities,
)
from quart import jsonify, request


async def get_available_external_entities(
    get_available_external_entities_uc: GetAvailableExternalEntities,
):
    country = request.args.get("country")
    if not country:
        return jsonify({"message": "Error: missing country"}), 400

    req = ExternalEntityCandidatesQuery(country=country, providers=None)
    result = await get_available_external_entities_uc.execute(req)

    return jsonify(result), 200
