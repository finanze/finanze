from flask import jsonify, request
from domain.use_cases.get_position import GetPosition
from domain.global_position import PositionQueryRequest

def positions(get_position: GetPosition):
    entities = request.args.getlist('entity')
    excluded_entities = request.args.getlist('excluded_entity')

    query = PositionQueryRequest(
        entities=[e for e in entities] or None,
        excluded_entities=[ee for ee in excluded_entities] or None
    )
    result = get_position.execute(query)
    return jsonify(result), 200
