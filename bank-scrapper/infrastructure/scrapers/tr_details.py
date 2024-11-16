from pytr.utils import preview


class Details:

    DATA_TYPES = [
        "stockDetails",
        "neonNews",
        "ticker",
        "performance",
        "instrument",
        "instrumentSuitability",
    ]

    def __init__(self, tr, isin):
        self.tr = tr
        self.isin = isin

    async def details_loop(self, data: list = DATA_TYPES):
        recv = 0
        await self.tr.stock_details(self.isin)
        await self.tr.news(self.isin)
        # await self.tr.subscribe_news(self.isin)
        await self.tr.ticker(self.isin, exchange="LSX")
        await self.tr.performance(self.isin, exchange="LSX")
        await self.tr.instrument_details(self.isin)
        await self.tr.instrument_suitability(self.isin)

        # await self.tr.add_watchlist(self.isin)
        # await self.tr.remove_watchlist(self.isin)
        # await self.tr.savings_plan_parameters(self.isin)
        # await self.tr.unsubscribe_news(self.isin)

        while True:
            _subscription_id, subscription, response = await self.tr.recv()

            if "stockDetails" in data and subscription["type"] == "stockDetails":
                recv += 1
                self.stockDetails = response
            elif "neonNews" in data and subscription["type"] == "neonNews":
                recv += 1
                self.neonNews = response
            elif "ticker" in data and subscription["type"] == "ticker":
                recv += 1
                self.ticker = response
            elif "performance" in data and subscription["type"] == "performance":
                recv += 1
                self.performance = response
            elif "instrument" in data and subscription["type"] == "instrument":
                recv += 1
                self.instrument = response
            elif (
                "instrumentSuitability" in data
                and subscription["type"] == "instrumentSuitability"
            ):
                recv += 1
                self.instrumentSuitability = response

            if recv == len(data):
                return
