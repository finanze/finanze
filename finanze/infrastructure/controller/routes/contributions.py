from domain.auto_contributions import ContributionQueryRequest
from domain.use_cases.get_contributions import GetContributions
from quart import jsonify, request


async def contributions(get_contributions: GetContributions):
    entities = request.args.getlist("entity")
    real_param = request.args.get("real")

    real = None
    if real_param is not None:
        if real_param.lower() == "true":
            real = True
        elif real_param.lower() == "false":
            real = False

    query = ContributionQueryRequest(
        entities=list(entities) or None,
        real=real,
    )
    result = await get_contributions.execute(query)
    return jsonify(result.contributions), 200
