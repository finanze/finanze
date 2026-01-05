import asyncio
import logging
import re
from decimal import ROUND_HALF_UP, Decimal

from infrastructure.client.entity.financial.tr.tr_timeline import preview


bond_pattern = re.compile(
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December|Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\.?\s+20\d{2}",
    re.IGNORECASE,
)


class Portfolio:
    def __init__(self, tr, include_watchlist=False):
        self.tr = tr
        self.include_watchlist = include_watchlist
        self.watchlist = None

        self._log = logging.getLogger(__name__)

    async def portfolio_loop(self):
        recv = 0
        await self.tr.compact_portfolio()
        recv += 1
        await self.tr.cash()
        recv += 1
        if self.include_watchlist:
            await self.tr.watchlist()
            recv += 1

        while recv > 0:
            subscription_id, subscription, response = await self.tr.recv()

            if subscription["type"] == "compactPortfolio":
                recv -= 1
                self.portfolio = response["positions"]
            elif subscription["type"] == "cash":
                recv -= 1
                self.cash = response
            elif subscription["type"] == "watchlist":
                recv -= 1
                self.watchlist = response
            else:
                print(
                    f"unmatched subscription of type '{subscription['type']}':\n{preview(response)}"
                )

            await self.tr.unsubscribe(subscription_id)

        isins = set()
        for pos in self.portfolio:
            isins.add(pos["instrumentId"])

        # extend portfolio with watchlist elements
        if self.watchlist:
            for pos in self.watchlist:
                isin = pos["instrumentId"]
                if isin not in isins:
                    isins.add(isin)
                    self.portfolio.append(pos)

        # Populate name for each ISIN
        subscriptions = {}
        for pos in self.portfolio:
            isin = pos["instrumentId"]
            subscription_id = await self.tr.instrument_details(isin)
            subscriptions[subscription_id] = pos

        while len(subscriptions) > 0:
            subscription_id, subscription, response = await self.tr.recv()

            if subscription["type"] == "instrument":
                await self.tr.unsubscribe(subscription_id)
                pos = subscriptions.pop(subscription_id, None)
                pos["name"] = response["shortName"]
                pos["exchangeIds"] = response["exchangeIds"]
            else:
                print(
                    f"unmatched subscription of type '{subscription['type']}':\n{preview(response)}"
                )

        # Get tickers and populate netValue for each ISIN
        self._log.info("Subscribing to tickers...")
        subscriptions = {}
        for pos in self.portfolio:
            isin = pos["instrumentId"]
            if len(pos["exchangeIds"]) > 0:
                subscription_id = await self.tr.ticker(
                    isin, exchange=pos["exchangeIds"][0]
                )
                subscriptions[subscription_id] = pos

        self._log.info("Waiting for tickers...")
        while len(subscriptions) > 0:
            try:
                subscription_id, subscription, response = await asyncio.wait_for(
                    self.tr.recv(), 5
                )
            except asyncio.TimeoutError:
                print("Timed out waiting for tickers")
                print(f"Remaining subscriptions: {subscriptions}")
                break

            if subscription["type"] == "ticker":
                await self.tr.unsubscribe(subscription_id)
                pos = subscriptions.pop(subscription_id, None)
                pos["price"] = response["last"]["price"]
                # Bond handling
                # Identify bonds by parsing the name - bond names are like "... month year"
                if bond_pattern.search(pos["name"]):
                    # Bond prices are per €100 face value
                    pos["price"] = Decimal(pos["price"]) / 100

                # watchlist positions don't have size/value
                if "netSize" not in pos:
                    pos["netSize"] = "0"
                    pos["averageBuyIn"] = pos["price"]
                pos["netValue"] = (
                    Decimal(pos["price"]) * Decimal(pos["netSize"])
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                print(
                    f"unmatched subscription of type '{subscription['type']}':\n{preview(response)}"
                )

        # sanitize - it can happen that we get no price, e.g. we ran into a timeout above or some instrument
        # does not deliver a price. Then we kick it out of the list and log this.
        portfolionew = []
        for pos in self.portfolio:
            if "price" not in pos:
                print(
                    f"Missing price for {pos['name']} ({pos['instrumentId']}), removing from result."
                )
            else:
                portfolionew.append(pos)
        self.portfolio = portfolionew
