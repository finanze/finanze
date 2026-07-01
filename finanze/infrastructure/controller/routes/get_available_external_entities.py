from domain.external_entity import ExternalEntityCandidatesQuery
from domain.external_integration import ExternalIntegrationId
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

    providers = None
    raw_provider = request.args.get("provider")
    if raw_provider:
        try:
            providers = [ExternalIntegrationId(raw_provider)]
        except ValueError:
            return jsonify({"message": "Error: invalid provider"}), 400

    req = ExternalEntityCandidatesQuery(country=country, providers=providers)
    result = await get_available_external_entities_uc.execute(req)

    return jsonify(result), 200
