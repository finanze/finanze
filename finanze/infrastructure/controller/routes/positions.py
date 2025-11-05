from domain.global_position import PositionQueryRequest
from domain.use_cases.get_position import GetPosition
from flask import jsonify, request


def positions(get_position: GetPosition):
    entities = request.args.getlist("entity")

    query = PositionQueryRequest(entities=list(entities) or None)
    result = get_position.execute(query)
    return jsonify(result), 200
