import logging
from datetime import date, datetime
from typing import Optional, Union

import requests
from cachetools import cached, TTLCache
from dateutil.relativedelta import relativedelta

from domain.scrap_result import LoginResult

DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


class UrbanitaeAPIClient:
    BASE_URL = "https://urbanitae.com/api"

    def __init__(self):
        self._headers = {}
        self._user_info = None
        self._log = logging.getLogger(__name__)

    def _execute_request(
            self, path: str, method: str, body: dict, raw: bool = False
    ) -> Union[dict, requests.Response]:
        response = requests.request(
            method, self.BASE_URL + path, json=body, headers=self._headers
        )

        if raw:
            return response

        if response.ok:
            return response.json()

        self._log.error("Error Status Code:", response.status_code)
        self._log.error("Error Response Body:", response.text)
        raise Exception("There was an error during the request")

    def _get_request(self, path: str) -> requests.Response:
        return self._execute_request(path, "GET", body=None)

    def _post_request(self, path: str, body: dict, raw: bool = False) -> Union[dict, requests.Response]:
        return self._execute_request(path, "POST", body=body, raw=raw)

    def login(self, username: str, password: str) -> dict:
        self._headers = dict()
        self._headers["Content-Type"] = "application/json"
        self._headers["User-Agent"] = (
            "Mozilla/5.0 (Linux; Android 11; moto g(20)) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/95.0.4638.74 Mobile Safari/537.36"
        )

        request = {
            "username": username,
            "password": password
        }
        response = self._post_request("/session", body=request, raw=True)

        if response.ok:
            response_body = response.json()
            if "token" not in response_body:
                return {"result": LoginResult.UNEXPECTED_ERROR, "message": "Token not found in response"}

            self._user_info = response_body
            self._headers["x-auth-token"] = response_body["token"]

            return {"result": LoginResult.CREATED}

        elif response.status_code == 401:
            return {"result": LoginResult.INVALID_CREDENTIALS}

        else:
            return {"result": LoginResult.UNEXPECTED_ERROR,
                    "message": f"Got unexpected response code {response.status_code}"}

    def get_user(self):
        return self._user_info

    def get_wallet(self):
        return self._get_request("/investor/wallet")

    def get_transactions(self,
                         from_date: Optional[date] = None,
                         to_date: Optional[date] = None):
        to_date = datetime.strftime(to_date or datetime.today(), DATETIME_FORMAT)
        from_date = datetime.strftime(
            from_date or (datetime.today() - relativedelta(years=5)), DATETIME_FORMAT
        )
        params = f"?page=0&size=1000&startDate={from_date}&endDate={to_date}"
        # "type"
        # 	MONEY_IN
        # 	MONEY_IN_CARD
        # 	MONEY_IN_WIRE
        # 	PREFUNDING_INVESTMENT_REFUND
        # 	INVESTMENT_REFUND
        # 	INVESTMENT_ERROR
        # 	RENTS
        # 	APPRECIATION
        # 	MGM_ADVOCATE
        # 	MGM_NEW_INVESTOR
        # 	MARKETING_REWARD
        # 	TRANSFER_NOTARY
        # 	P2P_IN
        # 	MONEY_OUT_WIRE
        # 	URBANITAE_FEE
        # 	CREDIT_CARD_FEE
        # 	NOTARY_REFUND
        # 	P2P_OUT
        # 	INVESTMENT
        # 	PREFUNDING_INVESTMENT
        # 	OVERFUNDING
        # 	OPERATOR
        # 	P2P
        # 	UNKNOWN
        return self._get_request(f"/investor/wallet/transactions{params}")["content"]

    def get_investments(self):
        params = "?page=0&size=1000&sortField=INVEST_DATE&sortDirection=DESC"
        return self._get_request(f"/investor/summary{params}")["content"]

    @cached(cache=TTLCache(maxsize=50, ttl=600))
    def get_project_detail(self, project_id: str):
        return self._get_request(f"/projects/{project_id}")

    def get_project_timeline(self, project_id: str):
        return self._get_request(f"/communications/timeline/project//{project_id}")
