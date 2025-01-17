from datetime import date
from typing import Optional, Union

import requests
from cachetools import cached, TTLCache
from dateutil.relativedelta import relativedelta

from domain.scrap_result import LoginResult

OLD_DATE_FORMAT = "%d/%m/%Y"


class MyInvestorAPIV1Client:
    BASE_URL = "https://app.myinvestor.es"

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
        response = self.__post_request("/ms-keycloak/api/v1/auth/token", body=request, raw=True)

        if response.ok:
            try:
                token = response.json()["payload"]["data"]["accessToken"]
            except KeyError:
                return {"result": LoginResult.UNEXPECTED_ERROR, "message": "Token not found in response"}

            self.__headers["Authorization"] = "Bearer " + token

            return {"result": LoginResult.CREATED}

        elif response.status_code == 400:
            return {"result": LoginResult.INVALID_CREDENTIALS}

        else:
            return {"result": LoginResult.UNEXPECTED_ERROR,
                    "message": f"Got unexpected response code {response.status_code}"}

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

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_accounts(self):
        return self.__get_request(
            "/myinvestor-server/rest/protected/cuentas/efectivo?soloActivas=true"
        )

    def get_account_remuneration(self, account_id):
        return self.__get_request(
            f"/myinvestor-server/rest/protected/cuentas/{account_id}/remuneracion"
        )

    def get_account_movements(self, account_id, from_date: Optional[date] = None, to_date: Optional[date] = None):
        to_date = date.strftime(to_date or date.today(), OLD_DATE_FORMAT)
        from_date = date.strftime(
            from_date or (date.today() - relativedelta(months=1)), OLD_DATE_FORMAT
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

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_sego_global_position(self):
        return self.__get_request("/ms-sego/api/v1/investments/self/global-position")["payload"][
            "data"
        ]

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_all_sego_investments(self):
        return self.__get_request("/ms-sego/api/v1/investments/self")["payload"]["data"]

    @cached(cache=TTLCache(maxsize=10, ttl=120))
    def get_sego_movements(self, page: int = 1):
        params = f"?limit=100&page={page}"
        return self.__get_request(f"/ms-sego/api/v1/investments/self/wallet/movements{params}")["payload"]["data"]

    def get_stocks_summary(self):
        return self.__get_request("/ms-broker/v1/acciones/resumen-acciones-cliente")

    def get_funds_and_portfolios_summary(self):
        return self.__get_request(
            "/myinvestor-server/rest/protected/inversiones?soloCarteras=false&soloActivas=true"
        )

    def get_stock_orders(self,
                         securities_account_id: str,
                         from_date: Optional[date] = None,
                         to_date: Optional[date] = None,
                         completed: bool = True):
        to_date = date.strftime(to_date or date.today(), OLD_DATE_FORMAT)
        from_date = date.strftime(
            from_date or (date.today().replace(month=1, day=1)), OLD_DATE_FORMAT
        )

        request = {
            "codigoIsin": None,
            "descendente": True,
            "estadoOrdenesEnum": "COMPLETADAS" if completed else "TODAS",
            "fecha_desde": from_date,
            "fecha_hasta": to_date,
            "filtroProducto": "ACCIONES_ETF",
            "idCuentaPensiones": None,
            "idCuentaValores": securities_account_id,
            "importeDesde": None,
            "importeHasta": None,
            "orden": None,
            "tipoOperacionEnum": None,
            "tipoOrdenesEnum": None,
        }

        return self.__post_request(
            "/ms-broker/v1/ordenes/obtenerOrdenes", body=request)

    def get_stock_order_details(self, order_id: str):
        return self.__get_request(f"/ms-broker/v1/ordenes/obtenerDetalleOrden/{order_id}")

    def get_fund_orders(self,
                        securities_account_id: str,
                        from_date: Optional[date] = None,
                        to_date: Optional[date] = None,
                        completed: bool = True):
        to_date = date.strftime(to_date or date.today(), OLD_DATE_FORMAT)
        from_date = date.strftime(
            from_date or (date.today().replace(month=1, day=1)), OLD_DATE_FORMAT
        )

        request = {
            "codigoIsin": None,
            "descendente": True,
            "estadoOrdenesEnum": "COMPLETADAS" if completed else "TODAS",
            "fecha_desde": from_date,
            "fecha_hasta": to_date,
            "filtroProducto": None,
            "idCuentaPensiones": None,
            "idCuentaValores": securities_account_id,
            "importeDesde": None,
            "importeHasta": None,
            "orden": None,
            "tipoOperacionEnum": None,
            "tipoOrdenesEnum": None,
        }

        return self.__post_request(
            "/myinvestor-server/rest/protected/fondos/consulta-ordenes", body=request)["listadoOperaciones"]

    def get_fund_order_details(self, order_id: str):
        return self.__get_request(f"/myinvestor-server/rest/protected/fondos/ordenes/{order_id}")

    def get_auto_contributions(self):
        return self.__get_request(
            "/myinvestor-server/rest/protected/aportaciones/list"
        )

    def get_deposits(self):
        return self.__get_request("/myinvestor-server/api/v2/deposits/self")["payload"]["data"]
