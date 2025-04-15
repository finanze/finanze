import json
import logging
import os
import pathlib
from datetime import datetime, timezone
from uuid import uuid4

import requests
from cachetools import TTLCache, cached

from domain.login_result import LoginResultCode

DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


class WecityAPIClient:
    BASE_OLD_URL = "https://www.wecity.com/"
    BASE_URL = "https://api.wecity.com/"

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._session_file = None

        session_file = os.environ.get("WC_SESSION_PATH")
        if session_file:
            self._session_file = pathlib.Path(session_file)

    def _get_request(self, path: str, api_url: bool = False) -> requests.Response:
        response = self._session.request("GET", (self.BASE_URL if api_url else self.BASE_OLD_URL) + path)

        if response.ok:
            return response.json()

        self._log.error("Error Status Code:", response.status_code)
        self._log.error("Error Response Body:", response.text)
        raise Exception("There was an error during the request")

    def _init_session(self):
        self._session = requests.Session()

        agent = (
            "Mozilla/5.0 (Linux; Android 11; moto g(20)) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/95.0.4638.74 Mobile Safari/537.36"
        )
        self._session.headers["User-Agent"] = agent

        if self._session_file and not self._session_file.parent.exists():
            self._session_file.parent.mkdir(parents=True, exist_ok=True)

    def login(self,
              username: str,
              password: str,
              avoid_new_login: bool = False,
              process_id: str = None,
              code: str = None) -> dict:

        self._init_session()

        if self._resume_web_session():
            self._log.debug("Web session resumed")
            return {"result": LoginResultCode.RESUMED}

        request = {
            "username": username,
            "password": password,
            "2facode": code or "",
            "browser_id": process_id
        }

        if code and process_id:
            if len(code) != 6:
                return {"result": LoginResultCode.INVALID_CODE}

            response = self._session.request("POST", self.BASE_URL + "/users/login", json=request)

            if not response.ok:
                return {"result": LoginResultCode.UNEXPECTED_ERROR, "message": "Unexpected response status code"}

            response = response.json()
            response_return = response.get("return", None)
            if not response_return:
                return {"result": LoginResultCode.UNEXPECTED_ERROR, "message": "Unexpected response content"}

            response_2factor = response_return.get("2factor", None)
            if response_2factor and "check 2fa" in response_2factor.lower():
                return {"result": LoginResultCode.INVALID_CODE}

            token = response_return.get("token", None)
            if not token:
                return {"result": LoginResultCode.UNEXPECTED_ERROR, "message": "Unexpected response content"}

            self._session.headers["x-auth-token"] = token

            sess_created_at = response_return.get("sess_time")
            sess_created_at = datetime.fromtimestamp(sess_created_at, tz=timezone.utc)
            sess_expiration = response_return.get("sess_expire")
            sess_expiration = datetime.fromtimestamp(sess_expiration, tz=timezone.utc)

            self._update_session_file(token, sess_created_at, sess_expiration)

            return {"result": LoginResultCode.CREATED}

        elif not process_id and not code:
            if not avoid_new_login:
                process_id = str(uuid4())
                request["browser_id"] = process_id

                response = self._session.request("POST", self.BASE_URL + "/users/login", json=request)

                if response.status_code == 401:
                    return {"result": LoginResultCode.INVALID_CREDENTIALS}

                if not response.ok:
                    return {"result": LoginResultCode.UNEXPECTED_ERROR, "message": "Unexpected response status code"}

                response = response.json()
                response_return = response.get("return", None)
                if not response_return:
                    return {"result": LoginResultCode.UNEXPECTED_ERROR, "message": "Unexpected response content"}

                response_2factor = response_return.get("2factor", None)
                if response_2factor and "check 2fa" in response_2factor.lower():
                    return {"result": LoginResultCode.CODE_REQUESTED, "processId": process_id}

                return {"result": LoginResultCode.UNEXPECTED_ERROR, "message": "Unexpected response content"}

            else:
                return {"result": LoginResultCode.NOT_LOGGED}

        else:
            raise ValueError("Invalid params")

    def _resume_web_session(self) -> bool:
        if not self._session_file or not self._session_file.exists():
            return False

        with self._session_file.open("r") as f:
            session_data = json.load(f)
            if not session_data:
                return False

            token = session_data["token"]
            expiration = datetime.fromisoformat(session_data["expiration"])
            if datetime.now(timezone.utc) >= expiration:
                return False

            self._session.headers["x-auth-token"] = token
            return True

    def _update_session_file(self, token, creation, expiration):
        if not self._session_file:
            return

        with self._session_file.open("w") as f:
            session_data = {
                "token": token,
                "creation": creation.isoformat(),
                "expiration": expiration.isoformat(),
            }
            json.dump(session_data, f)

    # @cached(cache=TTLCache(maxsize=1, ttl=120))
    # def get_user(self):
    #    return self._get_request("/ajax/ajax.php?option=checkuser")["data"]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_wallet(self):
        return self._get_request("/customers/me/wallet", api_url=True)["return"]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_investments(self):
        return self._get_request("/customers/me/invests-all", api_url=True)["return"]["data"]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_investment_details(self, investment_id: int):
        return self._get_request(f"/investments/{investment_id}/general", api_url=True)["return"]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_transactions(self):
        return self._get_request("/customers/me/transactions", api_url=True)["return"]
