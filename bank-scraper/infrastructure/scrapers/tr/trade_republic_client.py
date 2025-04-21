import logging
from datetime import datetime
from typing import Optional

import requests
from aiocache import cached
from dateutil.tz import tzlocal
from pytr.api import TradeRepublicApi
from pytr.portfolio import Portfolio
from requests import HTTPError
from requests.cookies import RequestsCookieJar, create_cookie

from domain.login import LoginResultCode, LoginResult, EntitySession, LoginOptions
from infrastructure.scrapers.tr.tr_details import TRDetails
from infrastructure.scrapers.tr.tr_timeline import TRTimeline


def _json_cookie_jar(jar: RequestsCookieJar) -> list:
    simple_cookies = []
    for cookie in jar:
        expires_timestamp = 0
        if cookie.expires is not None:
            try:
                expires_timestamp = int(cookie.expires)
            except (ValueError, TypeError):
                expires_timestamp = 0

        cookie_dict = {
            'name': cookie.name,
            'value': cookie.value,
            'domain': cookie.domain,
            'path': cookie.path,
            'expires': expires_timestamp,
            'secure': cookie.secure,
        }
        simple_cookies.append(cookie_dict)

    return simple_cookies


def _rebuild_cookie_jar(cookie_list: list) -> RequestsCookieJar:
    new_jar = RequestsCookieJar()

    for cookie_dict in cookie_list:
        if not all(k in cookie_dict for k in ('name', 'value', 'domain')):
            continue

        expires_ts = cookie_dict.get('expires')
        expires_arg = None if expires_ts == 0 else expires_ts

        args = {
            'name': cookie_dict['name'],
            'value': cookie_dict['value'],
            'domain': cookie_dict['domain'],
            'path': cookie_dict.get('path', '/'),
            'secure': cookie_dict.get('secure', False),
            'expires': expires_arg,
        }

        try:
            cookie = create_cookie(**args)
            cookie.domain_specified = bool(cookie.domain)
            cookie.path_specified = bool(cookie.path)
            new_jar.set_cookie(cookie)
        except Exception:
            pass

    return new_jar


class TradeRepublicClient:

    def __init__(self):
        self._tr_api = None
        self._log = logging.getLogger(__name__)

    def login(self,
              phone: str,
              pin: str,
              login_options: LoginOptions,
              process_id: str = None,
              code: str = None,
              session: Optional[EntitySession] = None) -> LoginResult:

        self._tr_api = TradeRepublicApi(
            phone_no=phone,
            pin=pin,
            locale="en",
            save_cookies=False,
        )

        if session and not login_options.force_new_session:
            self._inject_session(session)
            if self._resumable_session():
                self._log.debug("Resuming session")
                return LoginResult(LoginResultCode.RESUMED)

        if code and process_id:
            self._tr_api._process_id = process_id
            try:
                self._tr_api.complete_weblogin(code)
            except HTTPError as e:
                if e.response.status_code == 401:
                    return LoginResult(LoginResultCode.INVALID_CREDENTIALS)
                elif e.response.status_code == 400:
                    return LoginResult(LoginResultCode.INVALID_CODE)
                else:
                    self._log.error("Unexpected error during login", exc_info=e)
                    return LoginResult(LoginResultCode.UNEXPECTED_ERROR,
                                       message=f"Got unexpected error {e.response.status_code} during login")

            sess_created_at = datetime.now(tzlocal())
            session_payload = self._export_session()
            new_session = EntitySession(creation=sess_created_at,
                                        expiration=None,
                                        payload=session_payload)
            return LoginResult(LoginResultCode.CREATED, session=new_session)

        elif not code and not process_id:
            if not login_options.avoid_new_login:
                countdown = self._tr_api.inititate_weblogin()
                process_id = self._tr_api._process_id
                return LoginResult(LoginResultCode.CODE_REQUESTED,
                                   process_id=process_id,
                                   details={"countdown": countdown})
            else:
                return LoginResult(LoginResultCode.NOT_LOGGED)

        else:
            raise ValueError("Invalid login data")

    def _resumable_session(self) -> bool:
        try:
            self._tr_api.settings()
        except requests.exceptions.HTTPError:
            self._tr_api._weblogin = False
            return False
        else:
            return True

    def _export_session(self) -> dict:
        return {"cookies": _json_cookie_jar(self._tr_api._websession.cookies)}

    def _inject_session(self, session: EntitySession):
        cookies = _rebuild_cookie_jar(session.payload["cookies"])
        self._tr_api._websession.cookies = cookies
        self._tr_api._weblogin = True

    async def close(self):
        if self._tr_api and self._tr_api._ws:
            await self._tr_api._ws.close()

    @cached(ttl=120, noself=True)
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

    def get_user_info(self):
        return self._tr_api.settings()

    def get_interest_payouts(self, number_of_payouts: int):
        r = self._tr_api._web_request(f"/api/v1/banking/consumer/interest/payouts?numberOfPayouts={number_of_payouts}")
        r.raise_for_status()
        return r.json()

    def get_active_interest_rate(self):
        r = self._tr_api._web_request("/api/v1/banking/consumer/interest/rate")
        r.raise_for_status()
        return r.json()

    def get_interest_payout_summary(self, decimal_separator: str = ",", grouping_separator: str = "."):
        r = self._tr_api._web_request(
            f"/api/v1/interest/details-screen?decimalSeparator={decimal_separator}&groupingSeparator={grouping_separator}")
        r.raise_for_status()
        return r.json()
