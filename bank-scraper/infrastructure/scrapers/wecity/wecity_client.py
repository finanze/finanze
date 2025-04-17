import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

import requests
from cachetools import TTLCache, cached
from dateutil.tz import tzlocal

from domain.login import LoginResultCode, LoginResult, EntitySession, LoginOptions

DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


class WecityAPIClient:
    BASE_URL = "https://api.wecity.com/"

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def _get_request(self, path: str) -> dict:
        response = self._session.request("GET", self.BASE_URL + path)

        if response.ok:
            return response.json()

        self._log.error("Error Response Body:", response.text)
        response.raise_for_status()
        return {}

    def _init_session(self):
        self._session = requests.Session()

        agent = (
            "Mozilla/5.0 (Linux; Android 11; moto g(20)) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/95.0.4638.74 Mobile Safari/537.36"
        )
        self._session.headers["User-Agent"] = agent

    def login(self,
              username: str,
              password: str,
              login_options: LoginOptions,
              process_id: str = None,
              code: str = None,
              session: Optional[EntitySession] = None) -> LoginResult:

        self._init_session()
        now = datetime.now(tzlocal())

        if session and not login_options.force_new_session and now < session.expiration:
            self._inject_session(session)
            if self._resumable_session():
                self._log.debug("Resuming session")
                return LoginResult(LoginResultCode.RESUMED)

        request = {
            "username": username,
            "password": password,
            "2facode": code or "",
            "browser_id": process_id
        }

        if code and process_id:
            if len(code) != 6:
                return LoginResult(LoginResultCode.INVALID_CODE)

            response = self._session.request("POST", self.BASE_URL + "/users/login", json=request)

            if not response.ok:
                return LoginResult(LoginResultCode.UNEXPECTED_ERROR, message="Unexpected response status code")

            response = response.json()
            response_return = response.get("return", None)
            if not response_return:
                return LoginResult(LoginResultCode.UNEXPECTED_ERROR, message="Unexpected response content")

            response_2factor = response_return.get("2factor", None)
            if response_2factor and "check 2fa" in response_2factor.lower():
                return LoginResult(LoginResultCode.INVALID_CODE)

            token = response_return.get("token", None)
            if not token:
                return LoginResult(LoginResultCode.UNEXPECTED_ERROR, message="Unexpected response content")

            sess_created_at = datetime.fromtimestamp(response_return.get("sess_time"),
                                                     tz=tzlocal())  # This is provided with UTC tz
            sess_expiration = datetime.fromtimestamp(response_return.get("sess_expire"),
                                                     tz=tzlocal())  # I think this is not UTC, but Spain tz, as it is 2 days + diff
            session_payload = {"token": token}
            new_session = EntitySession(creation=sess_created_at,
                                        expiration=sess_expiration,
                                        payload=session_payload)

            self._inject_session(new_session)

            return LoginResult(LoginResultCode.CREATED, session=new_session)

        elif not process_id and not code:
            if not login_options.avoid_new_login:
                process_id = str(uuid4())
                request["browser_id"] = process_id

                response = self._session.request("POST", self.BASE_URL + "/users/login", json=request)

                if response.status_code == 401:
                    return LoginResult(LoginResultCode.INVALID_CREDENTIALS)

                if not response.ok:
                    return LoginResult(LoginResultCode.UNEXPECTED_ERROR, message="Unexpected response status code")

                response = response.json()
                response_return = response.get("return", None)
                if not response_return:
                    return LoginResult(LoginResultCode.UNEXPECTED_ERROR, message="Unexpected response content")

                response_2factor = response_return.get("2factor", None)
                if response_2factor and "check 2fa" in response_2factor.lower():
                    return LoginResult(LoginResultCode.CODE_REQUESTED, process_id=process_id)

                return LoginResult(LoginResultCode.UNEXPECTED_ERROR, message="Unexpected response content")

            else:
                return LoginResult(LoginResultCode.NOT_LOGGED)

        else:
            raise ValueError("Invalid params")

    def _resumable_session(self) -> bool:
        try:
            self._get_request("/customers/me/wallet")
        except requests.exceptions.HTTPError:
            return False
        else:
            return True

    def _inject_session(self, session: EntitySession):
        self._session.headers["x-auth-token"] = session.payload["token"]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_wallet(self):
        return self._get_request("/customers/me/wallet")["return"]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_investments(self):
        return self._get_request("/customers/me/invests-all")["return"]["data"]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_investment_details(self, investment_id: int):
        return self._get_request(f"/investments/{investment_id}/general")["return"]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_transactions(self):
        return self._get_request("/customers/me/transactions")["return"]
