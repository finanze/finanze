import json
import logging
from datetime import datetime, date
from typing import Optional

import tzlocal
from requests_toolbelt import MultipartEncoder

from domain.entity_login import EntityLoginResult, LoginResultCode
from infrastructure.client.http.http_session import new_http_session
from infrastructure.client.http.http_response import HttpResponse

DATE_FORMAT = "%Y-%m-%d"


class F24APIClient:
    BASE_URL = "https://freedom24.com"

    def __init__(self):
        self._session = None
        self._user_info = None
        self._log = logging.getLogger(__name__)

    async def _execute_request(
        self, path: str, method: str, data: str, headers: Optional[dict] = None
    ) -> dict:
        response = await self._session.request(
            method, self.BASE_URL + path, data=data, headers=headers
        )

        if response.ok:
            return await response.json()

        body = await response.text()
        self._log.error("Error Response Body:" + body)
        response.raise_for_status()
        return {}

    async def _post_request(
        self, path: str, data: str, headers: Optional[dict] = None
    ) -> dict:
        return await self._execute_request(path, "POST", data=data, headers=headers)

    async def _multi_part(self, path: str, data: dict) -> HttpResponse:
        multipart_data = MultipartEncoder(fields=data)

        return await self._session.post(
            self.BASE_URL + path,
            content=multipart_data.to_string(),
            headers={"Content-Type": multipart_data.content_type},
        )

    async def _request_login(
        self, username: str, password: str, user_id: Optional[str] = None
    ) -> HttpResponse:
        timezone = {
            "timezone": tzlocal.get_localzone_name(),
            "offset": str(datetime.now().astimezone().utcoffset().seconds // 3600 * -1),
        }

        data = {
            "login": username,
            "password": password,
            "rememberMe": "true",
            "mode": "regular",
            "timezone": json.dumps(timezone),
        }

        if user_id:
            data["userId"] = user_id
        else:
            data["getAccounts"] = "true"

        return await self._multi_part(
            "/authentication/ajax-check-login-password", data=data
        )

    async def login(self, username: str, password: str) -> EntityLoginResult:
        self._session = new_http_session()
        self._session.headers["Origin"] = self.BASE_URL

        first_login_response = await self._request_login(username, password)

        if first_login_response.ok:
            response_body = await first_login_response.json()
            if "error" in response_body:
                error = response_body["error"].strip()
                if "Incorrect e-mail or password" in error:
                    return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
                else:
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR, message=error
                    )
            else:
                self._user_info = response_body
        else:
            body = await first_login_response.text()
            if "maintenance" in body:
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Entity portal under maintenance",
                )

            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected response code {first_login_response.status}",
            )

        user_id = None
        accounts = self._user_info["accounts"]
        for acc in accounts:
            if acc["account_type"] == "brokerage":
                user_id = str(acc["user_id"])
                break

        login_response = await self._request_login(username, password, user_id)

        if login_response.ok:
            response_body = await login_response.json()
            if "error" in response_body:
                error = response_body["error"].strip()
                if "Incorrect e-mail or password" in error:
                    return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
                else:
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR, message=error
                    )
            else:
                if (
                    response_body["success"]
                    and response_body["logged"]
                    and response_body["SID"]
                ):
                    return EntityLoginResult(LoginResultCode.CREATED)
                self._log.error(response_body)
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR, message="Got unexpected response"
                )
        else:
            await login_response.text()
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected response code {login_response.status}",
            )

    def get_user_info(self) -> dict:
        return self._user_info

    async def get_cash_flows(self) -> dict:
        data = {"q": '{"cmd":"getUserCashFlows","params":{"filter":{}}}'}
        resp = await self._multi_part("/api", data=data)
        return await resp.json()

    async def get_positions(self, user_id: str) -> dict:
        data = (
            'q={"cmd":"getUserPositions","params":{"requestedUserId":' + user_id + "}}"
        )
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        return await self._post_request("/api", data=data, headers=headers)

    async def get_trades(self, user_id: str) -> dict:
        data = f"user_id={user_id}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        return await self._post_request(
            "/portfolios/ajax-get-trades/", data=data, headers=headers
        )

    async def get_off_balance(self) -> dict:
        data = {"q": '{"cmd":"getOffBalanceAssets","params":{}}'}
        resp = await self._multi_part("/api?cmd=getOffBalanceAssets", data=data)
        return await resp.json()

    async def get_orders_history(
        self,
        from_date: date,
        to_date: Optional[date] = None,
        skip: int = 0,
        take: int = 1000,
    ) -> dict:
        to_date_str = date.strftime(to_date or date.today(), DATE_FORMAT)

        data = {
            "q": """
            {
                "cmd": "getOrdersHistory",
                "params": {
                    "from": "%s",
                    "order": 1,
                    "page": {
                        "skip": %s,
                        "take": %s
                    },
                    "sort": 0,
                    "till": "%s"
                }
            }
        """
            % (from_date, skip, take, to_date_str)
        }
        resp = await self._multi_part("/api?cmd=getOrdersHistory", data=data)
        return await resp.json()

    async def switch_user(self, trader_systems_id: str):
        data = (
            'q={"cmd":"switchToConnectedUser","params":{"trader_systems_id":"'
            + trader_systems_id
            + '"}}'
        )
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        return await self._post_request(
            "/api?cmd=switchToConnectedUser", data=data, headers=headers
        )

    async def get_connected_users_assets(self):
        data = {"q": '{"cmd":"getConnectedUsersAssets"}'}
        resp = await self._multi_part("/api?cmd=getConnectedUsersAssets", data=data)
        return await resp.json()

    async def find_by_ticker(self, ticker: str):
        data = (
            'q={"cmd":"tickerFinder","params":{"text":"'
            + ticker
            + '","exchanges":"MCX,SPBEX,FORTS,EASTE,FIX,SPBFOR,UFORTS,UFOUND,EU,ATHEX,BIST,KASE,AIX,ITS,HKEX,EUROBOND,CRPT,IMEX"}}'
        )
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        return await self._post_request("/api", data=data, headers=headers)
