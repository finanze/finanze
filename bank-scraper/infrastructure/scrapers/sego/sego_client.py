import codecs
import logging
from typing import Union

import requests
from cachetools import TTLCache, cached

from domain.login_result import LoginResultCode


class SegoAPIClient:
    BASE_URL = "https://apim-sego-core-prod.azure-api.net"

    API_KEY = '2r73914170s440ooo8r60qrq6s77n41n'

    def __init__(self):
        self._headers = {}
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

    def login(self,
              username: str,
              password: str,
              avoid_new_login: bool = False,
              code: str = None) -> dict:

        self._headers = dict()
        self._headers["Content-Type"] = "application/json"
        self._headers["Ocp-Apim-Subscription-Key"] = codecs.decode(self.API_KEY, 'rot_13')
        self._headers["User-Agent"] = (
            "Mozilla/5.0 (Linux; Android 11; moto g(20)) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/95.0.4638.74 Mobile Safari/537.36"
        )

        request = {
            "codigoPlataforma": "web-sego",
            "email": username,
            "password": password,
            "tipoTfaCodigo": "login"
        }

        if code:
            request["codigoSMS"] = code

        response = self._post_request("/core/v1/Login/Inversor", body=request, raw=True)

        if response.ok:
            response_body = response.json()
            if response_body["isCodigoEnviado"]:
                if avoid_new_login:
                    return {"result": LoginResultCode.NOT_LOGGED}

                return {"result": LoginResultCode.CODE_REQUESTED}

            if "token" not in response_body:
                return {"result": LoginResultCode.UNEXPECTED_ERROR, "message": "Token not found in response"}

            self._headers["Authorization"] = "Bearer " + response_body["token"]
            return {"result": LoginResultCode.CREATED}

        elif response.status_code == 400:
            if code:
                return {"result": LoginResultCode.INVALID_CODE}
            else:
                return {"result": LoginResultCode.INVALID_CREDENTIALS}

        else:
            return {"result": LoginResultCode.UNEXPECTED_ERROR,
                    "message": f"Got unexpected response code {response.status_code}"}

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
        return self._post_request("/factoring/v1/Inversiones/Filter", body=request)["list"]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_pending_investments(self):
        return self._get_request("/factoring/v1/Inversiones/Pendientes")

    @cached(cache=TTLCache(maxsize=10, ttl=120))
    def get_movements(self, page: int = 1, limit: int = 100):
        if limit > 100:
            raise ValueError("Limit cannot be greater than 100")

        params = f"?page={page}&limit=100"
        return self._get_request(f"/core/v1/Wallet/Transactions{params}")
