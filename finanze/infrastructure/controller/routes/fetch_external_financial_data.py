from uuid import UUID

from domain.external_entity import ExternalFetchRequest
from domain.use_cases.fetch_external_financial_data import FetchExternalFinancialData
from flask import jsonify


async def fetch_external_financial_data(
    fetch_external_financial_data_uc: FetchExternalFinancialData,
    external_entity_id: str,
):
    try:
        external_entity_id = UUID(external_entity_id)
    except ValueError:
        return jsonify({"message": "Invalid external entity ID"}), 400

    fetch_request = ExternalFetchRequest(
        external_entity_id=external_entity_id,
    )
    result = await fetch_external_financial_data_uc.execute(fetch_request)

    response = {"code": result.code}
    if result.details:
        response["details"] = result.details
    if result.data:
        response["data"] = result.data

    return jsonify(response), 200
