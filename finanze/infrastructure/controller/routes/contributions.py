from flask import jsonify, request

from domain.auto_contributions import ContributionQueryRequest
from domain.use_cases.get_contributions import GetContributions


def contributions(get_contributions: GetContributions):
    entities = request.args.getlist("entity")
    excluded_entities = request.args.getlist("excluded_entity")
    real_param = request.args.get("real")

    real = None
    if real_param is not None:
        if real_param.lower() == "true":
            real = True
        elif real_param.lower() == "false":
            real = False

    query = ContributionQueryRequest(
        entities=[e for e in entities] or None,
        excluded_entities=[ee for ee in excluded_entities] or None,
        real=real,
    )
    result = get_contributions.execute(query)
    return jsonify(result.contributions), 200
