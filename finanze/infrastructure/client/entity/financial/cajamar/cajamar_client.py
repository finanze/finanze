import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

import requests
import time
from dateutil.tz import tzlocal

from domain.entity_login import EntityLoginResult, EntitySession, LoginResultCode

PREFIX = "110003"
BASE_PREFIX = "0003"
SUFFIX = "99"
RANDOM_MAX = 1000
DEVICE_ID_LENGTH = 25

ACCESS_TOKEN_LIFETIME = 15 * 60  # 20 minutes (but set to 15)
REFRESH_TOKEN_LIFETIME = 4 * 30 - 1  # Days


def _calculate_c_digit(base: str) -> str:
    sum_even_idx = 0
    sum_odd_idx = 0
    for i, ch in enumerate(base):
        d = int(ch)
        if i % 2 == 0:
            sum_even_idx += d
        else:
            sum_odd_idx += d
    raw = ((sum_even_idx * 3) + sum_odd_idx) % 10
    c_digit = 0 if raw == 0 else 10 - raw
    return str(c_digit)


def _generate_device_id() -> str:
    timestamp = str(int(time.time() * 1000))
    rand_val = secrets.randbelow(RANDOM_MAX)
    random3 = f"{rand_val:03d}"
    base_for_check = BASE_PREFIX + timestamp + random3
    check_digit = _calculate_c_digit(base_for_check)
    device_id = PREFIX + timestamp + random3 + check_digit + SUFFIX
    return device_id


class CajamarClient:
    BASE_URL = "https://api.cajamar.es/amea-web/abh"
    API_VERSION = "/v19.39.0"
    APP_VERSION = "1.134.17"

    def __init__(self):
        self._headers = {}
        user_agent = "Dalvik/2.1.0 (Linux; U; Android 10; LG G2 Build/XX98)"
        self._headers["User-Agent"] = user_agent
        self._headers["Content-Type"] = "application/json"

        self._device_id = None
        self._session_expiration = None
        self._log = logging.getLogger(__name__)

    def login(
        self,
        username: str,
        password: str,
        session: Optional[EntitySession],
        retry: bool = False,
    ) -> EntityLoginResult:
        refresh_token_expiration = (
            datetime.fromisoformat(session.payload.get("refresh_token_expiration"))
            if session
            else None
        )
        should_enroll = not session or refresh_token_expiration <= datetime.now(
            tzlocal()
        )

        self._device_id = session.payload.get("device_id") if session else None
        self._headers["deviceid"] = self._device_id
        access_token = session.payload.get("access_token") if session else None
        refresh_token = session.payload.get("refresh_token") if session else None

        if should_enroll:
            if not self._device_id:
                self._device_id = _generate_device_id()
            self._headers["deviceid"] = self._device_id

            auth_response = self._enrollment(username, password)
            body = auth_response.json()
            if auth_response.status_code == 403:
                if body and "code" in body:
                    code = body.get("code", "")
                    if code == "E1002":
                        return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

                self._log.error(f"Got body {auth_response.text}")
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Got unexpected body in response code {auth_response.status_code} while enrolling",
                )

            elif auth_response.ok:
                if "accessToken" in body or "refreshToken" in body:
                    access_token = body["accessToken"]
                    refresh_token = body["refreshToken"]
                    refresh_token_expiration = (
                        self._calculate_refresh_token_expiration()
                    )
                else:
                    self._log.error(f"Got body {auth_response.text}")
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR,
                        message="Tokens not found in response",
                    )
            else:
                self._log.error(f"Got body {auth_response.text}")
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Got unexpected response code {auth_response.status_code} while enrolling",
                )

        self._set_auth_header(access_token)

        login_response = self._login(password)
        if login_response.status_code == 401:
            refresh_response = self._refresh_token(refresh_token)
            if refresh_response.ok:
                body = refresh_response.json()
                if "accessToken" in body or "refreshToken" in body:
                    access_token = body["accessToken"]
                    refresh_token = body["refreshToken"]
                    refresh_token_expiration = (
                        self._calculate_refresh_token_expiration()
                    )
                    self._set_auth_header(access_token)
                else:
                    self._log.error(f"Got body {refresh_response.text}")
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR,
                        message="Tokens not found in refresh response",
                    )
            else:
                if not retry:
                    old_refresh_token_exp = datetime.now(tzlocal()) - timedelta(
                        seconds=1
                    )
                    self._headers.pop("Authorization", None)
                    session.payload = {
                        "device_id": self._device_id,
                        "refresh_token_expiration": old_refresh_token_exp.isoformat(),
                    }
                    self._log.info(
                        "Reenrolling in Cajamar due to invalid refresh token"
                    )
                    return self.login(username, password, session, retry=True)

                self._log.error(f"Got body {refresh_response.text}")
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Got unexpected response code {refresh_response.status_code} while refreshing token after reauthentication",
                )

            login_response = self._login(password)
            if login_response.status_code == 401:
                body = login_response.json()
                if body and "code" in body:
                    code = body.get("code", "")
                    if code == "SYS060":
                        return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

                self._log.error(f"Got body {login_response.text}")
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Got unexpected body in response code {login_response.status_code} while logging in after refresh",
                )

        if not login_response.ok:
            self._log.error(f"Got body {login_response.text}")
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected response code {login_response.status_code} while logging in",
            )

        payload = {
            "device_id": self._device_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "refresh_token_expiration": refresh_token_expiration.isoformat(),
        }
        new_session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=refresh_token_expiration,
            payload=payload,
        )

        return EntityLoginResult(LoginResultCode.CREATED, session=new_session)

    @staticmethod
    def _calculate_refresh_token_expiration() -> datetime:
        return datetime.now(tzlocal()) + timedelta(days=REFRESH_TOKEN_LIFETIME)

    @staticmethod
    def _calculate_access_token_expiration() -> datetime:
        return datetime.now(tzlocal()) + timedelta(seconds=ACCESS_TOKEN_LIFETIME)

    def _set_auth_header(self, access_token: str):
        self._headers["Authorization"] = f"Bearer {access_token}"

    def _execute_request(
        self,
        path: str,
        method: str,
        body: dict,
        params: dict,
        headers: dict = None,
        raw: bool = False,
    ) -> dict | str | requests.Response:
        headers = headers or self._headers
        response = requests.request(
            method, self.BASE_URL + path, json=body, params=params, headers=headers
        )

        if raw:
            return response

        if response.ok:
            return response.json()

        self._log.error("Error Response Body: " + response.text)
        response.raise_for_status()
        return {}

    def _post_request(
        self,
        path: str,
        body: object = None,
        params=None,
        headers: dict = None,
        raw=False,
    ) -> dict | requests.Response:
        return self._execute_request(
            path, "POST", body=body, headers=headers, raw=raw, params=params
        )

    def _enrollment(self, username: str, password: str):
        data = {
            "appName": "WEFFERENT",
            "appVersion": self.APP_VERSION,
            "deviceId": self._device_id,
            "deviceName": "LG G2",
            "hasScreenLock": True,
            "jailbreak": False,
            "language": "eng",
            "osName": "ANDROID",
            "osVersion": "29 (10)",
            "password": password,
            "screenHeight": 1920,
            "screenWidth": 1080,
            "user": username,
        }

        return self._post_request("/enrollment", body=data, raw=True)

    def _login(self, password: str):
        data = {
            "appVersion": "1.134.17",
            "deviceName": "LG G2",
            "hasScreenLock": True,
            "jailbreak": False,
            "language": "eng",
            "osVersion": "29 (10)",
            "password": password,
            "screenHeight": 1920,
            "screenWidth": 1080,
        }

        return self._post_request("/login", body=data, raw=True)

    def _refresh_token(self, refresh_token: str):
        headers = self._headers.copy()
        headers["Authorization"] = f"Bearer {refresh_token}"
        return self._post_request("/refreshToken", headers=headers, raw=True)

    def get_user(self):
        return self._post_request(self.API_VERSION + "/wall/userid")

    def get_position(self):
        return self._post_request(self.API_VERSION + "/position")

    def get_account_details(self, account_id: str):
        return self._post_request(self.API_VERSION + "/account/" + account_id)

    def get_account_txs(self, account_id: str, page_num: int = 1, page_size: int = 16):
        params = {"pageNumber": page_num, "pageSize": page_size}
        return self._post_request(
            self.API_VERSION + f"/account/{account_id}/transactions",
            params=params,
        )

    def get_account_direct_debits(self, account_id: str):
        return self._post_request(
            self.API_VERSION + f"/account/{account_id}/directDebits"
        )

    def get_card(self, card_id: str):
        return self._post_request(self.API_VERSION + f"/card/{card_id}")

    def get_card_txs(self, card_id: str, page_num: int = 1, page_size: int = 16):
        params = {"pageNumber": page_num, "pageSize": page_size}
        return self._post_request(
            self.API_VERSION + f"/card/{card_id}/transactions", params=params
        )

    def get_loan(self, loan_account_id: str):
        params = {"arorigin": "C"}
        return self._post_request(
            self.API_VERSION + f"/account/{loan_account_id}/loan", params=params
        )

    def get_loan_statements(
        self, loan_account_id: str, page_num: int = 1, page_size: int = 16
    ):
        params = {"pageNumber": page_num, "pageSize": page_size}
        return self._post_request(
            self.API_VERSION + f"/account/{loan_account_id}/statements",
            params=params,
        )

    def get_company_capital_contributions(self):
        return self._post_request(self.API_VERSION + "/companyCapital/contributions")
