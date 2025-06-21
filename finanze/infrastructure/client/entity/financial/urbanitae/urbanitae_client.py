import base64
import codecs
import logging
from datetime import date, datetime
from typing import Optional

import pyaes
import requests
from cachetools import cached, TTLCache
from dateutil.relativedelta import relativedelta

from domain.entity_login import EntityLoginResult, LoginResultCode

DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


def _pkcs7_pad(data: bytes, block_size: int) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def _generate_iv(date: datetime) -> bytes:
    day = str(date.day).zfill(2)
    month = str(date.month).zfill(2)
    year = str(date.year)

    iv_string = f"DD{day}MM{month}YYYY{year}"

    return iv_string.encode("utf-8")


class UrbanitaeAPIClient:
    BASE_URL = "https://urbanitae.com/api"

    PASSWORD_ENCRYPTION_KEY = "9ZJtHA1fYAr1w2nT"

    def __init__(self):
        self._headers = {}
        self._user_info = None
        self._log = logging.getLogger(__name__)

    def _execute_request(
        self, path: str, method: str, body: dict, raw: bool = False
    ) -> dict | requests.Response:
        response = requests.request(
            method, self.BASE_URL + path, json=body, headers=self._headers
        )

        if raw:
            return response

        if response.ok:
            return response.json()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}

    def _get_request(self, path: str) -> requests.Response:
        return self._execute_request(path, "GET", body=None)

    def _post_request(
        self, path: str, body: dict, raw: bool = False
    ) -> dict | requests.Response:
        return self._execute_request(path, "POST", body=body, raw=raw)

    def login(self, username: str, password: str) -> EntityLoginResult:
        self._headers = dict()
        self._headers["Content-Type"] = "application/json"
        self._headers["User-Agent"] = (
            "Mozilla/5.0 (Linux; Android 11; moto g(20)) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/95.0.4638.74 Mobile Safari/537.36"
        )

        request = {"username": username, "password": self._encrypt_password(password)}
        response = self._post_request("/session", body=request, raw=True)

        if response.ok:
            response_body = response.json()
            if "token" not in response_body:
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Token not found in response",
                )

            self._user_info = response_body
            self._headers["x-auth-token"] = response_body["token"]

            return EntityLoginResult(LoginResultCode.CREATED)

        elif response.status_code == 401:
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

        else:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected response code {response.status_code}",
            )

    def _encrypt_password(self, password: str) -> str:
        key = str.encode(codecs.decode(self.PASSWORD_ENCRYPTION_KEY, "rot_13"))
        iv = _generate_iv(datetime.now())
        password_bytes = password.encode("utf-8")
        padded_data = _pkcs7_pad(password_bytes, 16)
        aes = pyaes.AESModeOfOperationCBC(key, iv=iv)
        encrypted_data = aes.encrypt(padded_data)
        return base64.b64encode(encrypted_data).decode("utf-8")

    def get_user(self):
        return self._user_info

    def get_wallet(self):
        return self._get_request("/investor/wallet")

    def get_transactions(
        self,
        page: int = 0,
        limit: int = 1000,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ):
        to_date = datetime.strftime(to_date or datetime.today(), DATETIME_FORMAT)
        from_date = datetime.strftime(
            from_date or (datetime.today() - relativedelta(years=5)), DATETIME_FORMAT
        )
        params = f"?page={page}&size={limit}&startDate={from_date}&endDate={to_date}"
        # "type"
        # 	MONEY_IN - INBOUND
        # 	MONEY_IN_CARD - INBOUND
        # 	MONEY_IN_WIRE - INBOUND
        # 	PREFUNDING_INVESTMENT_REFUND - INBOUND
        # 	INVESTMENT_REFUND - INBOUND
        # 	INVESTMENT_ERROR - INBOUND
        # 	RENTS - INBOUND
        # 	APPRECIATION - INBOUND
        # 	MGM_ADVOCATE - INBOUND
        # 	MGM_NEW_INVESTOR - INBOUND
        # 	MARKETING_REWARD - INBOUND
        # 	TRANSFER_NOTARY - INBOUND
        # 	P2P_IN - INBOUND
        # 	MONEY_OUT_WIRE - OUTBOUND
        # 	URBANITAE_FEE - OUTBOUND
        # 	CREDIT_CARD_FEE - OUTBOUND
        # 	NOTARY_REFUND - OUTBOUND
        # 	P2P_OUT - OUTBOUND
        # 	INVESTMENT - OUTBOUND (INVESTMENT)
        # 	PREFUNDING_INVESTMENT - OUTBOUND (INVESTMENT)
        # 	OVERFUNDING
        # 	OPERATOR
        # 	P2P
        # 	UNKNOWN
        return self._get_request(f"/investor/wallet/transactions{params}")["content"]

    def get_investments(
        self, page: int = 0, limit: int = 1000, project_phases: list[str] = None
    ):
        params = f"?page={page}&size={limit}&sortField=INVEST_DATE&sortDirection=DESC"
        if project_phases:
            params += "&projectPhases=" + ",".join(project_phases)
        return self._get_request(f"/investor/summary{params}")["content"]

    @cached(cache=TTLCache(maxsize=50, ttl=600))
    def get_project_detail(self, project_id: str):
        return self._get_request(f"/projects/{project_id}")

    def get_project_timeline(self, project_id: str):
        return self._get_request(f"/communications/timeline/project//{project_id}")
