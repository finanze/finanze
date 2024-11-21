from datetime import date

import requests
from dateutil.relativedelta import relativedelta

OLD_DATE_FORMAT = "%d/%m/%Y"


class MyInvestorAPIClient:
    BASE_URL = "https://app.myinvestor.es"

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
        self.__headers["Referer"] = self.BASE_URL
        self.__headers["x-origin-b2b"] = self.BASE_URL
        self.__headers["User-Agent"] = (
            "Mozilla/5.0 (Linux; Android 11; moto g(20)) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/95.0.4638.74 Mobile Safari/537.36"
        )

        request = {
            "customerId": username,
            "accessType": "USERNAME",
            "password": password,
            "deviceId": "c768ee05-6abf-48aa-a7f2-dbc601da265f",
            "platform": None,
            "otpId": None,
            "code": None,
        }
        response = self.__post_request("/ms-keycloak/api/v1/auth/token", body=request)
        self.__headers["Authorization"] = (
                "Bearer " + response["payload"]["data"]["accessToken"]
        )

    def check_maintenance(self):
        request = {
            "usuario": None,
            "deviceId": None,
            "plataforma": "browser",
            "codigoPeticionOTP": None,
            "codigoOTPRecibido": "",
            "cotitular": False,
            "tipoLogin": "USUARIO",
            "hashApp": None,
            "contrasena": None,
        }
        response = self.__post_request(
            "/myinvestor-server/rest/public/mantenimientos/check-mantenimiento",
            body=request,
        )
        return response

    def get_user(self):
        return self.__get_request(
            "/myinvestor-server/rest/protected/usuarios/usuario-logueado"
        )

    def get_accounts(self):
        return self.__get_request(
            "/myinvestor-server/rest/protected/cuentas/efectivo?soloActivas=true"
        )

    def get_account_remuneration(self, account_id):
        return self.__get_request(
            f"/myinvestor-server/rest/protected/cuentas/{account_id}/remuneracion"
        )

    def get_account_movements(self, account_id, from_date=None, to_date=None):
        to_date = to_date or date.strftime(date.today(), OLD_DATE_FORMAT)
        from_date = from_date or date.strftime(
            date.today() - relativedelta(months=1), OLD_DATE_FORMAT
        )

        request = {
            "idCuenta": account_id,
            "fechaDesde": from_date,
            "fechaHasta": to_date,
            "tipoMovimientoEnum": None,
            "importeDesde": None,
            "importeHasta": None,
            "concepto": None,
            "referenciaMovimiento": None,
        }

        return self.__post_request(
            "/myinvestor-server/rest/protected/cuentas/consulta-movimientos-efectivo",
            body=request,
        )

    def get_cards(self, account_id=None):
        params = f"?accountId={account_id}" if account_id else ""
        return self.__get_request(f"/ms-cards/api/v1/cards{params}")["payload"]["data"]

    def get_card_transactions(self, card_id):
        return self.__get_request(f"/ms-cards/api/v1/cards/{card_id}/transaction")[
            "payload"
        ]["data"]

    def get_sego_global_position(self):
        return self.__get_request("/ms-sego/api/v1/investments/self/global-position")["payload"][
            "data"
        ]

    def get_active_sego_investments(self):
        return self.__get_request(
            "/ms-sego/api/v1/investments/self?operationStateCodes=DISPUTE&operationStateCodes=MANAGING_COLLECTION"
            "&operationStateCodes=NOT_ARRIVING_COLLECTION_DATE"
        )["payload"]["data"]

    def get_finished_sego_investments(self):
        return self.__get_request(
            "/ms-sego/api/v1/investments/self?operationStateCodes=CASHED&operationStateCodes=FAILED"
        )["payload"]["data"]

    def get_stocks_summary(self):
        return self.__get_request("/ms-broker/v1/acciones/resumen-acciones-cliente")

    def get_funds_and_portfolios_summary(self):
        return self.__get_request(
            "/myinvestor-server/rest/protected/inversiones?soloCarteras=false&soloActivas=true"
        )

    def get_deposits(self):
        return self.__get_request("/myinvestor-server/api/v2/deposits/self")["payload"]["data"]
