from quart import jsonify

from domain.use_cases.update_tracked_quotes import UpdateTrackedQuotes


async def update_tracked_quotes(update_tracked_quotes_uc: UpdateTrackedQuotes):
    result = await update_tracked_quotes_uc.execute()
    return (
        jsonify(
            {
                "hadTracked": result.had_tracked,
                "changed": result.changed,
                "changedEntities": [str(eid) for eid in result.changed_entities],
                "throttled": result.throttled,
            }
        ),
        200,
    )
