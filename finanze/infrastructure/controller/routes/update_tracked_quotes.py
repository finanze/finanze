from domain.use_cases.update_tracked_quotes import UpdateTrackedQuotes


async def update_tracked_quotes(update_tracked_quotes_uc: UpdateTrackedQuotes):
    await update_tracked_quotes_uc.execute()
    return "", 204
