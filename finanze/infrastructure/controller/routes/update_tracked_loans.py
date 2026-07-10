from quart import jsonify

from domain.use_cases.update_tracked_loans import UpdateTrackedLoans


async def update_tracked_loans(update_tracked_loans_uc: UpdateTrackedLoans):
    result = await update_tracked_loans_uc.execute()
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
