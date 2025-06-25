import logging
from datetime import date
from typing import Optional

import requests
from cachetools import cached, TTLCache
from dateutil.relativedelta import relativedelta

from domain.login import LoginResult, LoginResultCode

GET_DATE_FORMAT = "%Y%m%d"
DATE_FORMAT = "%Y-%m-%d"


class MyInvestorAPIV2Client:
    LOGIN_URL = "https://api.myinvestor.es"
    BASE_URL = "https://app.myinvestor.es"

    def __init__(self):
        self._headers = {}
        self._log = logging.getLogger(__name__)

    def _execute_request(
        self,
        path: str,
        method: str,
        body: dict,
        raw: bool = False,
        base_url: str = BASE_URL,
    ) -> dict | requests.Response:
        response = requests.request(
            method, base_url + path, json=body, headers=self._headers
        )

        if raw:
            return response

        if response.ok:
            return response.json()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}

    def _get_request(self, path: str, base_url: str = BASE_URL) -> requests.Response:
        return self._execute_request(path, "GET", body=None, base_url=base_url)

    def _post_request(
        self, path: str, body: dict, raw: bool = False, base_url: str = BASE_URL
    ) -> dict | requests.Response:
        return self._execute_request(
            path, "POST", body=body, raw=raw, base_url=base_url
        )

    def login(self, username: str, password: str) -> LoginResult:
        self._headers = dict()
        self._headers["Content-Type"] = "application/json"
        self._headers["Referer"] = self.BASE_URL
        self._headers["x-origin-b2b"] = self.BASE_URL
        self._headers["User-Agent"] = (
            "Mozilla/5.0 (Linux; Android 11; moto g(20)) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/95.0.4638.74 Mobile Safari/537.36"
        )

        request = {
            "customerId": username,
            "accessType": "USERNAME",
            "password": password,
            "deviceId": "c768ee05-6abf-48aa-a7f2-dbc601da265f",
            "platform": None,
            "otpId": None,
            "code": None,
        }
        response = self._post_request(
            "/login/api/v1/auth/token", body=request, raw=True, base_url=self.LOGIN_URL
        )

        if response.ok:
            try:
                token = response.json()["payload"]["data"]["accessToken"]
            except KeyError:
                return LoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Token not found in response",
                )
            self._headers["Authorization"] = "Bearer " + token
            return LoginResult(LoginResultCode.CREATED)
        elif response.status_code == 400:
            return LoginResult(LoginResultCode.INVALID_CREDENTIALS)
        else:
            return LoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected response code {response.status_code}",
            )

    def check_maintenance(self):
        return requests.get("https://cms.myinvestor.es/api/maintenances").json()["data"]

    def get_user(self):
        return self._get_request("/myinvestor-server/api/v3/customers/self")["payload"][
            "data"
        ]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_cash_accounts(self):
        return self._get_request("/myinvestor-server/api/v2/cash-accounts/self")[
            "payload"
        ]["data"]

    def get_account_remuneration(self, account_id):
        return self._get_request(
            f"/myinvestor-server/api/v2/cash-accounts/{account_id}/remuneration"
        )["payload"]["data"]

    def get_account_movements(
        self,
        account_id,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        concept: Optional[str] = None,
        amount_from: Optional[float] = None,
        amount_to: Optional[float] = None,
        flow_type: Optional[str] = None,
    ):
        to_date = date.strftime(to_date or date.today(), GET_DATE_FORMAT)
        from_date = date.strftime(
            from_date or (date.today() - relativedelta(months=1)), GET_DATE_FORMAT
        )

        path = f"/myinvestor-server/api/v2/cash-accounts/{account_id}/flows?dateFrom={from_date}&dateTo={to_date}"

        if concept:
            path += f"&concept={concept}"

        if amount_from:
            path += f"&amountFrom={amount_from}"

        if amount_to:
            path += f"&amountTo={amount_to}"

        if flow_type:
            path += f"&flowType={flow_type}"  # IN, OUT

        return self._get_request(path)["payload"]["data"]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_security_accounts(self):
        return self._get_request(
            "/myinvestor-server/api/v2/securities-accounts/self-basic"
        )["payload"]["data"]

    def get_cards(self, account_id=None):
        params = f"?accountId={account_id}" if account_id else ""
        return self._get_request(f"/ms-cards/api/v1/cards{params}")["payload"]["data"]

    def get_card_totals(self, card_id):
        return self._get_request(f"/ms-cards/api/v1/cards/{card_id}/totals")["payload"][
            "data"
        ]

    def get_security_account_details(self, security_account_id: str):
        return self._get_request(
            f"/myinvestor-server/api/v2/securities-accounts/{security_account_id}"
        )["payload"]["data"]

    def get_stock_orders(
        self,
        securities_account_id: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        status: Optional[str] = "COMPLETE",
        tx_type: Optional[str] = "ALL",
        isin: Optional[str] = None,
    ):
        to_date = date.strftime(to_date or date.today(), DATE_FORMAT)
        from_date = date.strftime(
            from_date or (date.today().replace(month=1, day=1)), DATE_FORMAT
        )

        path = f"/ms-broker/v2/stock-orders?stockAccountId={securities_account_id}&dateFrom={from_date}&dateTo={to_date}"

        if tx_type:
            path += f"&type={tx_type}"  # RECURRENT ON_DEMAND ALL

        if status:
            path += f"&status={status}"  # COMPLETE PENDING REJECTED CANCEL

        if isin:
            path += f"&isin={isin}"

        return self._get_request(path)["payload"]["data"]

    def get_stock_order_details(self, order_id: str):
        return self._get_request(f"/ms-broker/v2/stock-orders/{order_id}")["payload"][
            "data"
        ]

    def get_fund_orders(
        self,
        securities_account_id: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        status: Optional[str] = "COMPLETE",
        tx_type: Optional[str] = None,
        from_amount: Optional[float] = None,
        to_amount: Optional[float] = None,
        isin: Optional[str] = None,
    ):
        to_date = date.strftime(to_date or date.today(), GET_DATE_FORMAT)
        from_date = date.strftime(
            from_date or (date.today().replace(month=1, day=1)), GET_DATE_FORMAT
        )

        path = f"/myinvestor-server/api/v2/securities-accounts/{securities_account_id}/orders?dateFrom={from_date}&dateTo={to_date}"

        if tx_type:
            path += f"&type={tx_type}"  # PERIODIC ORDINARY None (=ALL)

        if status:
            path += f"&status={status}"  # COMPLETE PENDING REJECTED CANCEL IN_PROGRESS

        if from_amount:
            path += f"&amountFrom={from_amount}"

        if to_amount:
            path += f"&amountTo={to_amount}"

        if isin:
            path += f"&isin={isin}"

        return self._get_request(path)["payload"]["data"]

    def get_fund_order_details(self, order_id: str):
        return self._get_request(
            f"/myinvestor-server/api/v2/securities-accounts/self/orders/{order_id}"
        )["payload"]["data"]

    def get_auto_contributions(self):
        return self._get_request(
            "/myinvestor-server/api/v2/automatic-contributions/self"
        )["payload"]["data"]

    def get_deposits(self):
        return self._get_request("/myinvestor-server/api/v2/deposits/self")["payload"][
            "data"
        ]

    def is_portfolio_pledged(self, security_account_id: str):
        return self._get_request(
            f"/ms-lending/api/v2/pledged/guarantees/portfolios/{security_account_id}/status"
        )["payload"]["data"]["isPledged"]

    def is_fund_pledged(self, security_account_id: str, fund_isin: str):
        return self._get_request(
            f"/ms-lending/api/v2/pledged/guarantees/securities-accounts/{security_account_id}/funds/{fund_isin}"
        )["payload"]["data"]["isPledged"]
