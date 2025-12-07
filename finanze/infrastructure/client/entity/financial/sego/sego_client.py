import codecs
import logging
import re
from datetime import datetime
from typing import Optional

import requests
from cachetools import TTLCache, cached
from dateutil.tz import tzlocal

from domain.entity_login import (
    LoginResultCode,
    EntityLoginResult,
    EntitySession,
    LoginOptions,
)

EXPIRATION_DATETIME_REGEX = r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.?\d{0,6})\d*(.*)$"


def _parse_expiration_datetime(expiration: str) -> Optional[datetime]:
    match = re.match(EXPIRATION_DATETIME_REGEX, expiration)
    if match:
        truncated_date_string = match.group(1) + match.group(2)
        format_code = "%Y-%m-%dT%H:%M:%S.%f%z"
        try:
            return datetime.strptime(truncated_date_string, format_code)
        except ValueError:
            return None
    return None


class SegoAPIClient:
    BASE_URL = "https://api.segofinance.com"

    API_KEY = "3215739s71p549r6no77368ps1o40rp8"

    def __init__(self):
        self._headers = {}
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

    def _init_session(self):
        self._headers = dict()
        self._headers["Content-Type"] = "application/json"
        self._headers["Ocp-Apim-Subscription-Key"] = codecs.decode(
            self.API_KEY, "rot_13"
        )
        self._headers["User-Agent"] = (
            "Mozilla/5.0 (Linux; Android 11; moto g(20)) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/95.0.4638.74 Mobile Safari/537.36"
        )

    def login(
        self,
        username: str,
        password: str,
        login_options: LoginOptions,
        code: str = None,
        session: Optional[EntitySession] = None,
    ) -> EntityLoginResult:
        self._init_session()

        now = datetime.now(tzlocal())

        if session and not login_options.force_new_session and now < session.expiration:
            self._inject_session(session)
            if self._resumable_session():
                self._log.debug("Resuming session")
                return EntityLoginResult(LoginResultCode.RESUMED)

        request = {
            "plataforma": "web-sego",
            "email": username,
            "password": password,
            "tipoTfaCodigo": "login",
        }

        if code:
            request["codigoSMS"] = code
        elif login_options.avoid_new_login:
            return EntityLoginResult(LoginResultCode.NOT_LOGGED)

        response = self._post_request("/core/v1/Login/Inversor", body=request, raw=True)

        if response.ok:
            response_body = response.json()
            if response_body["isCodigoEnviado"]:
                return EntityLoginResult(LoginResultCode.CODE_REQUESTED)

            if "token" not in response_body:
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Token not found in response",
                )

            sess_created_at = datetime.now(tzlocal())
            sess_expiration = _parse_expiration_datetime(
                response_body.get("expirationDate")
            )
            session_payload = {"token": response_body["token"]}
            new_session = EntitySession(
                creation=sess_created_at,
                expiration=sess_expiration,
                payload=session_payload,
            )

            self._inject_session(new_session)

            return EntityLoginResult(LoginResultCode.CREATED, session=new_session)

        elif response.status_code == 400:
            if code:
                return EntityLoginResult(LoginResultCode.INVALID_CODE)
            else:
                return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

        else:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected response code {response.status_code}",
            )

    def _resumable_session(self) -> bool:
        try:
            self._get_request("/core/v1/InformacionBasica")
        except requests.exceptions.HTTPError:
            return False
        else:
            return True

    def _inject_session(self, session: EntitySession):
        self._headers["Authorization"] = "Bearer " + session.payload["token"]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_user(self):
        return self._get_request("/core/v1/InformacionBasica")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_wallet(self):
        return self._get_request("/core/v1/wallet")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_investments(self, states: set[str] = frozenset([])):
        states = list(states)

        request = {
            "tipoEstadoOperacionCodigoArray": states,
            "tipoEstadoRondaCodigo": "",
            "tipoOperacionCodigoArray": [],
            "empresaDeudoraId": 0,
            "order": "",
            "orderColumn": "",
            "limit": 1000,
            "page": 0,
        }
        return self._post_request("/factoring/v1/Inversiones/Filter", body=request)[
            "list"
        ]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_pending_investments(self):
        return self._get_request("/factoring/v1/Inversiones/Pendientes")

    @cached(cache=TTLCache(maxsize=10, ttl=120))
    def get_movements(self, page: int = 1, limit: int = 100):
        if limit > 100:
            raise ValueError("Limit cannot be greater than 100")

        params = f"?page={page}&limit=100"
        return self._get_request(f"/core/v1/Wallet/Transactions{params}")
