import json
import logging
import os
import pathlib
import re
from http.cookiejar import MozillaCookieJar, Cookie

import requests
from cachetools import TTLCache, cached

from domain.scrap_result import LoginResult

DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


class WecityAPIClient:
    BASE_OLD_URL = "https://www.wecity.com/"
    BASE_URL = "https://api.wecity.com/"

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def _get_request(self, path: str, api_url: bool = False) -> requests.Response:
        response = self._session.request("GET", (self.BASE_URL if api_url else self.BASE_OLD_URL) + path)

        if response.ok:
            return response.json()

        self._log.error("Error Status Code:", response.status_code)
        self._log.error("Error Response Body:", response.text)
        raise Exception("There was an error during the request")

    def _init_session(self):
        self._session = requests.Session()

        cookies_file = os.environ["WC_COOKIES_PATH"]
        self._cookies_file = pathlib.Path(cookies_file)

        agent = (
            "Mozilla/5.0 (Linux; Android 11; moto g(20)) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/95.0.4638.74 Mobile Safari/537.36"
        )
        self._session.headers["User-Agent"] = agent

        if not self._cookies_file.parent.exists():
            self._cookies_file.parent.mkdir(parents=True, exist_ok=True)
        self._session.cookies = MozillaCookieJar(self._cookies_file)

    def login(self,
              username: str,
              password: str,
              avoid_new_login: bool = False,
              process_id: str = None,
              code: str = None) -> dict:

        self._init_session()

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        if self._resume_web_session():
            self._log.debug("Web session resumed")
            return {"result": LoginResult.RESUMED, "message": "Resumed stored session"}

        if code and process_id:
            if len(code) != 6:
                return {"result": LoginResult.INVALID_CODE}

            body = ""
            for pos in range(len(code)):
                body += f"sms_{pos + 1}={code[pos]}&"

            body += "sms_code=&boton-2factor="

            session_cookie = Cookie(0, name="PHPSESSID", value=process_id, port=None, port_specified=False,
                                    domain="www.wecity.com", domain_specified=True, domain_initial_dot=True,
                                    path="/", path_specified=True, secure=False, expires=None, discard=False,
                                    comment=None, comment_url=None, rest={})
            self._session.cookies.set_cookie(session_cookie)
            response = self._session.request("POST", self.BASE_OLD_URL + "/login", data=body, headers=headers)

            if not response.ok:
                return {"result": LoginResult.UNEXPECTED_ERROR, "message": "Unexpected response status code"}

            response_text = response.text
            if "El código introducido no es correcto" in response_text:
                return {"result": LoginResult.INVALID_CODE}

            if "Entrar en mi cuenta" in response_text:
                return {"result": LoginResult.UNEXPECTED_ERROR, "message": "Unexpected response content"}

            self._session.cookies.save(ignore_discard=True, ignore_expires=True)
            self._add_auth_headers()

            return {"result": LoginResult.CREATED}

        elif not process_id and not code:
            if not avoid_new_login:
                body = f"usuario={username}&password={password}&boton-login="
                response = self._session.request("POST", self.BASE_OLD_URL + "/login", data=body, headers=headers)

                if not response.ok:
                    return {"result": LoginResult.UNEXPECTED_ERROR, "message": "Unexpected response status code"}

                response_text = response.text
                if "Tu usuario o contraseña no son correctos" in response_text:
                    return {"result": LoginResult.INVALID_CREDENTIALS}

                if "Doble Factor de Autenticación" in response_text:
                    process_id = requests.utils.dict_from_cookiejar(self._session.cookies)["PHPSESSID"]
                    return {"result": LoginResult.CODE_REQUESTED, "processId": process_id}

                pattern = r"localStorage\.setItem\('CapacitorStorage\.user',\s*'(.*?)'\);"
                match = re.search(pattern, response.text)
                if match:
                    json_str = match.group(1).encode('utf-8').decode('unicode_escape')
                    try:
                        user_data = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        self._log.debug(e)
                        self._log.debug(json_str)
                        return {"result": LoginResult.UNEXPECTED_ERROR, "message": "Error parsing user data"}

                    token = user_data.get("data", {}).get("token")
                    if not token:
                        self._log.debug(user_data)
                        return {"result": LoginResult.UNEXPECTED_ERROR, "message": "Token not found when refreshing"}

                    self._log.debug(f"Refreshing session with {token[:5]}...")
                    self._add_auth_headers(token)

                    return {"result": LoginResult.RESUMED, "message": "Resumed web session"}

                self._log.debug(response_text)
                return {"result": LoginResult.UNEXPECTED_ERROR, "message": "Unexpected response content"}

            else:
                return {"result": LoginResult.NOT_LOGGED}

        else:
            raise ValueError("Invalid params")

    def _resume_web_session(self):
        if self._cookies_file.exists():
            self._session.cookies.load(ignore_discard=True, ignore_expires=True)
            return self._add_auth_headers()
        return False

    def _add_auth_headers(self, token: str = None):
        try:
            if not token:
                user_data = self.get_user()
                if user_data:
                    token = user_data["token"]
                else:
                    self._log.debug("User data not available")
                    return False

            self._session.headers["x-auth-token"] = token
            return True
        except requests.exceptions.HTTPError:
            return False

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_user(self):
        return self._get_request("/ajax/ajax.php?option=checkuser")["data"]

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
