from domain.global_position import PositionQueryRequest
from domain.use_cases.get_position import GetPosition
from quart import jsonify, request


async def positions(get_position: GetPosition):
    entities = request.args.getlist("entity")

    query = PositionQueryRequest(entities=list(entities) or None)
    result = await get_position.execute(query)
    return jsonify(result), 200
