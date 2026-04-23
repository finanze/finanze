from uuid import UUID

from domain.entity import Feature
from domain.fetch_result import FetchOptions, FetchRequest
from domain.use_cases.fetch_crypto_data import FetchCryptoData
from quart import jsonify, request


async def fetch_crypto_data(fetch_crypto_data_uc: FetchCryptoData):
    body = await request.get_json()

    entity = body.get("entity", None)
    if entity:
        entity = UUID(entity)

    deep = body.get("deep", False)

    fetch_request = FetchRequest(
        entity_id=entity,
        features=[Feature.POSITION],
        fetch_options=FetchOptions(deep=deep),
    )
    result = await fetch_crypto_data_uc.execute(fetch_request)

    response = {"code": result.code}
    if result.details:
        response["details"] = result.details
    if result.data:
        response["data"] = result.data

    return jsonify(response), 200
