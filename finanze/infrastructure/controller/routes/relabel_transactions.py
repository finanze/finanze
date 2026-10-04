from domain.use_cases.relabel_transactions import RelabelTransactions
from infrastructure.controller.mappers.labeling_mapper import map_relabel_request
from quart import jsonify, request


async def relabel_transactions(relabel_transactions_uc: RelabelTransactions):
    body = await request.get_json()
    try:
        relabel_request = map_relabel_request(body or {})
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    result = await relabel_transactions_uc.execute(relabel_request)
    return jsonify(result), 200
