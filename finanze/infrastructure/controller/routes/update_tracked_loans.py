from domain.use_cases.update_tracked_loans import UpdateTrackedLoans


async def update_tracked_loans(update_tracked_loans_uc: UpdateTrackedLoans):
    await update_tracked_loans_uc.execute()
    return "", 204
