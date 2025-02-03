import logging
import os
from datetime import datetime
from typing import Optional

from cachetools import TTLCache, cached
from pytr.api import TradeRepublicApi
from pytr.portfolio import Portfolio
from requests import HTTPError

from domain.scrap_result import LoginResult
from infrastructure.scrapers.tr.tr_details import TRDetails
from infrastructure.scrapers.tr.tr_timeline import TRTimeline


class TradeRepublicClient:

    def __init__(self):
        self._tr_api = None
        self._cookies_file = os.environ["TR_COOKIES_PATH"]
        self._log = logging.getLogger(__name__)

    def login(self,
              phone: str,
              pin: str,
              avoid_new_login: bool = False,
              process_id: str = None,
              code: str = None) -> dict:

        self._tr_api = TradeRepublicApi(
            phone_no=phone,
            pin=pin,
            locale="en",
            save_cookies=True,
            cookies_file=self._cookies_file,
        )

        if self._tr_api.resume_websession():
            self._log.info("Web session resumed")
            return {"result": LoginResult.RESUMED}

        else:
            if code and process_id:
                self._tr_api._process_id = process_id
                try:
                    self._tr_api.complete_weblogin(code)
                except HTTPError as e:
                    if e.response.status_code == 401:
                        return {"result": LoginResult.INVALID_CREDENTIALS}
                    elif e.response.status_code == 400:
                        return {"result": LoginResult.INVALID_CODE}
                    else:
                        self._log.error("Unexpected error during login", exc_info=e)
                        return {"result": LoginResult.UNEXPECTED_ERROR,
                                "message": f"Got unexpected error {e.response.status_code} during login"}

                return {"result": LoginResult.CREATED}

            elif not code and not process_id:
                if not avoid_new_login:
                    countdown = self._tr_api.inititate_weblogin()
                    process_id = self._tr_api._process_id
                    return {"result": LoginResult.CODE_REQUESTED, "countdown": countdown, "processId": process_id}
                else:
                    return {"result": LoginResult.NOT_LOGGED}

            else:
                raise ValueError("Invalid login data")

    async def close(self):
        await self._tr_api._ws.close()

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    async def get_portfolio(self):
        portfolio = Portfolio(self._tr_api)
        await portfolio.portfolio_loop()
        return portfolio

    async def get_details(self, isin: str, types: list = ["stockDetails", "instrument"]):
        details = TRDetails(self._tr_api, isin)
        await details.fetch(types)
        return details

    async def get_transactions(self, since: Optional[datetime] = None, already_registered_ids: set[str] = None):
        dl = TRTimeline(self._tr_api,
                        since=since,
                        requested_data=["timelineTransactions", "timelineDetailV2"],
                        already_registered_ids=already_registered_ids)
        return await dl.fetch()
