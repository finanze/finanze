from typing import Union

import requests

from domain.scrap_result import LoginResult


class SegoAPIClient:
    BASE_URL = "https://apim-sego-core-prod.azure-api.net"

    def __init__(self):
        self.__headers = {}

    def __execute_request(
            self, path: str, method: str, body: dict, raw: bool = False
    ) -> Union[dict, requests.Response]:
        response = requests.request(
            method, self.BASE_URL + path, json=body, headers=self.__headers
        )

        if raw:
            return response

        if response.ok:
            return response.json()

        print("Error Status Code:", response.status_code)
        print("Error Response Body:", response.text)
        raise Exception("There was an error during the request")

    def __get_request(self, path: str) -> requests.Response:
        return self.__execute_request(path, "GET", body=None)

    def __post_request(self, path: str, body: dict, raw: bool = False) -> Union[dict, requests.Response]:
        return self.__execute_request(path, "POST", body=body, raw=raw)

    def login(self, username: str, password: str) -> dict:
        self.__headers = dict()
        self.__headers["Content-Type"] = "application/json"
        self.__headers["Ocp-Apim-Subscription-Key"] = "2e73914170f440bbb8e60ded6f77a41a"
        self.__headers["User-Agent"] = (
            "Mozilla/5.0 (Linux; Android 11; moto g(20)) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/95.0.4638.74 Mobile Safari/537.36"
        )

        request = {
            "codigoPlataforma": "web-sego",
            "email": username,
            "password": password,
            "tipoTfaCodigo": "login",
        }
        response = self.__post_request("/core/v1/Login/Inversor", body=request, raw=True)

        if response.ok:
            response_body = response.json()
            if "token" not in response_body:
                return {"result": LoginResult.UNEXPECTED_ERROR, "message": "Token not found in response"}

            self.__headers["Authorization"] = "Bearer " + response_body["token"]
            return {"result": LoginResult.CREATED}

        elif response.status_code == 400:
            return {"result": LoginResult.INVALID_CREDENTIALS}

        else:
            return {"result": LoginResult.UNEXPECTED_ERROR,
                    "message": f"Got unexpected response code {response.status_code}"}

    def get_user(self):
        return self.__get_request("/core/v1/InformacionBasica")

    def get_wallet(self):
        return self.__get_request("/core/v1/wallet")

    def get_investments(self, states: list[str] = []):
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
        return self.__post_request("/factoring/v1/Inversiones/Filter", body=request)["list"]

    def get_pending_investments(self):
        return self.__get_request("/factoring/v1/Inversiones/Pendientes")

    def get_movements(self, page: int = 0):
        params = f"?page={page}&limit=100"
        return self.__get_request(f"/core/v1/Wallet/Transactions{params}")
