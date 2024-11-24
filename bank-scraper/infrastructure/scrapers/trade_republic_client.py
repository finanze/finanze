import os
from datetime import datetime
from typing import Optional

from pytr.api import TradeRepublicApi
from pytr.portfolio import Portfolio
from pytr.utils import get_logger

from infrastructure.scrapers.tr_details import TRDetails
from infrastructure.scrapers.tr_timeline import TRTimeline


class TradeRepublicClient:

    def __init__(self):
        self.__tr_api = None
        self.__cookies_file = os.environ["TR_COOKIES_PATH"]

    def login(self, phone: str, pin: str, process_id: str = None, code: str = None) -> Optional[dict]:
        log = get_logger(__name__)

        self.__tr_api = TradeRepublicApi(
            phone_no=phone,
            pin=pin,
            locale="en",
            save_cookies=True,
            cookies_file=self.__cookies_file,
        )

        if self.__tr_api.resume_websession():
            log.info("Web session resumed")
            return None

        else:
            if code and process_id:
                self.__tr_api._process_id = process_id
                self.__tr_api.complete_weblogin(code)
                return None

            elif not code and not process_id:
                countdown = self.__tr_api.inititate_weblogin()
                process_id = self.__tr_api._process_id
                return {"countdown": countdown, "processId": process_id}

            else:
                raise ValueError("Invalid login data")

    async def get_portfolio(self):
        portfolio = Portfolio(self.__tr_api)
        await portfolio.portfolio_loop()
        return portfolio

    async def get_details(self, isin: str, types: list = ["stockDetails", "instrument"]):
        details = TRDetails(self.__tr_api, isin)
        await details.details_loop(types)
        return details

    async def get_transactions(self, since: Optional[datetime] = None, already_registered_ids: set[str] = None):
        dl = TRTimeline(self.__tr_api,
                        since=since,
                        requested_data=["timelineTransactions", "timelineDetailV2"],
                        already_registered_ids=already_registered_ids)
        return await dl.fetch()
