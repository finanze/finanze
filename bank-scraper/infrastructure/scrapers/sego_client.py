import requests


class SegoAPIClient:
    BASE_URL = "https://apim-sego-core-prod.azure-api.net"

    def __init__(self):
        self.__headers = {}

    def __execute_request(
            self, path: str, method: str, body: dict
    ) -> requests.Response:
        response = requests.request(
            method, self.BASE_URL + path, json=body, headers=self.__headers
        )

        if response.status_code == 200:
            return response.json()

        print("Error Status Code:", response.status_code)
        print("Error Response Body:", response.text)
        raise Exception("There was an error during the request")

    def __get_request(self, path: str) -> requests.Response:
        return self.__execute_request(path, "GET", body=None)

    def __post_request(self, path: str, body: dict) -> requests.Response:
        return self.__execute_request(path, "POST", body=body)

    def login(self, username: str, password: str):
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
        response = self.__post_request("/core/v1/Login/Inversor", body=request)
        self.__headers["Authorization"] = "Bearer " + response["token"]

        return response

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
