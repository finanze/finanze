import logging
import re
from datetime import datetime, date
from typing import Optional

import pyDes
from bs4 import BeautifulSoup
from curl_cffi import requests
from dateutil.relativedelta import relativedelta

from domain.entity_login import EntityLoginResult, LoginResultCode

REQUEST_DATE_FORMAT = "%Y-%m-%d"


def _encrypt_password(key: str, password: str):
    return (
        pyDes.des(key, mode=pyDes.CBC, IV="00000000", pad="\0")
        .encrypt(password)
        .hex()
        .upper()
    )


class UnicajaClient:
    BASE_URL = "https://univia.unicajabanco.es"
    AUTH_PATH = "/services/rest/autenticacion"

    LOAN_KEY_MAPPING = {
        "Tipo de préstamo:": "loanType",
        "Plazo/período:": "termPeriod",
        "Interés:": "interestRate",
        "Estado:": "status",
        "Fecha solicitud:": "applicationDate",
        "Fecha de apertura:": "openingDate",
        "Fecha de próximo recibo:": "nextPaymentDate",
        "Fecha de vencimiento:": "maturityDate",
        "Fecha de próxima revisión:": "nextReviewDate",
        "Cuota actual:": "currentInstallment",
        "Importe del préstamo:": "loanAmount",
        "Capital pagado:": "principalPaid",
        "Capital pendiente:": "principalOutstanding",
        "Deuda pendiente de pago:": "outstandingDebt",
        "Importe mínimo:": "minimumAmount",
        "Comisión por entrega:": "deliveryFee",
        "Comisión por cancelación:": "cancellationFee",
    }

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def login(self, username: str, password: str, abck: str) -> EntityLoginResult:
        if not abck:
            return EntityLoginResult(code=LoginResultCode.LOGIN_REQUIRED,
                                     message="abck is required for automated login, but it was not provided")

        user_agent = "Mozilla/5.0 (Linux; Android 5.1.1; Lenovo PB1-750M) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36"
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent

        ck = self._ck()

        self._session.cookies.set("_abck", abck)

        encoded_password = _encrypt_password(ck, password)
        auth_response = self.auth(username, encoded_password)

        if auth_response.ok:
            auth_response_body = auth_response.json()

            if "tokenCSRF" not in auth_response_body:
                return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR, message="Token not found in response")

            self._session.headers["tokenCSRF"] = auth_response_body["tokenCSRF"]
            self._session.headers["Content-Type"] = "application/x-www-form-urlencoded"

            return EntityLoginResult(LoginResultCode.CREATED)

        elif auth_response.status_code == 400:
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

        elif auth_response.status_code == 403:
            return EntityLoginResult(LoginResultCode.LOGIN_REQUIRED, message="abck may not be valid anymore")

        else:
            return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR,
                                     message=f"Got unexpected response code {auth_response.status_code}")

    def _execute_request(
            self,
            path: str,
            method: str,
            body: dict,
            params: dict,
            json: bool = True,
            raw: bool = False,
    ) -> dict | str | requests.Response:
        response = self._session.request(
            method, self.BASE_URL + path, data=body, params=params
        )

        if raw:
            return response

        if response.ok:
            if json:
                return response.json()
            else:
                return response.content.decode('windows-1252')

        self._log.error("Error Response Body: " + response.text)
        response.raise_for_status()
        return {}

    def _get_request(
            self, path: str, params: dict = None, json: bool = True
    ) -> dict | str:
        return self._execute_request(path, "GET", body=None, json=json, params=params)

    def _post_request(
            self, path: str, body: object, raw=False
    ) -> dict | requests.Response:
        return self._execute_request(path, "POST", body=body, json=True, raw=raw, params=None)

    def _ck(self):
        return self._get_request("/services/rest/openapi/ck")["ck"]

    def auth(self, username: str, encoded_password: str):
        data = {
            "idioma": "es",
            "usuario": username,
            "password": encoded_password,
            "origen": "bdigital",
        }
        return self._post_request(self.AUTH_PATH, body=data, raw=True)

    def get_user(self):
        return self._get_request("/services/rest/perfilusuario")

    def list_accounts(self):
        return self._get_request("/services/rest/api/productos/listacuentas")

    def get_account_movements(self, ppp: str):
        # account_movs_request = {"ppp": ppp, "indOperacion": "I"}
        account_movs_request = {
            "ppp": ppp,
            "saldoUltMov": "283.57",
            "numUltMov": "1097",
            "indOperacion": "P",
        }
        return self._post_request(
            "/services/rest/api/cuentas/listadoMovimientos", account_movs_request
        )

    def get_account_movement(self, ppp: str, nummov: str):
        return self._get_request(
            f"/services/rest/api/cuentas/movimientos/detallemovimiento?ppp={ppp}&nummov={nummov}"
        )

    def get_cards(self):
        return self._get_request("/services/rest/api/productos/listatarjetas")

    def get_card(self, ppp: str, card_type: str):
        card_details_request = {"ppp": ppp, "tipotarjeta": card_type}
        return self._post_request(
            "/services/rest/api/tarjetas/detalleTarjeta", card_details_request
        )

    def get_card_config(self, ppp: str):
        card_config_request = {"ppp": ppp}
        return self._post_request(
            "/services/rest/api/tarjetas/configuracionUso/datos", card_config_request
        )

    def get_card_movements(self, ppp: str, from_date: Optional[date] = None):
        from_date = date.strftime(
            from_date or (date.today() - relativedelta(months=1)), REQUEST_DATE_FORMAT
        )
        card_movs_request = {"ppp": ppp, "fechaDesde": from_date, "impDesde": "0"}
        return self._post_request(
            "/services/rest/api/tarjetas/movimientos/listadoMovimientos/v2",
            card_movs_request,
        )

    def get_loans(self):
        return self._get_request("/services/rest/api/productos/listaprestamos")

    def get_loan(self, p: str, ppp: str):
        loan_request = {"o": "dpres", "p": p, "ppp": ppp}
        response = self._get_request(
            "/services/servlet/OpWeb",
            params=loan_request,
            json=False,
        )

        soup = BeautifulSoup(response, "html.parser")

        loan_data = {}

        def clean_text(text):
            return " ".join(text.split()).replace("\xa0", " ")

        def format_value(value):
            if "EUR" in value:
                value = value.replace("EUR", "").strip()
                value = value.replace(".", "").replace(",", ".")
                return float(value)

            elif "%" in value:
                value = re.split(r"[\s%]", value)[0].replace(",", ".")
                return float(value) / 100

            try:
                return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
            except ValueError:
                pass

            return value

        tables = soup.find_all("table", class_="td-bgcolor5")
        if not tables:
            return None

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                columns = row.find_all("td")
                if len(columns) >= 2:
                    spanish_key = clean_text(columns[0].get_text())
                    value = clean_text(columns[1].get_text())

                    english_key = self.LOAN_KEY_MAPPING.get(spanish_key)

                    if english_key:
                        loan_data[english_key] = format_value(value)

        return loan_data

    def get_transfers_summary(self):
        return self._get_request("/services/rest/api/transferencias/resumen")

    def get_transfers_historic(self, from_date: Optional[date] = None, to_date: Optional[date] = None):
        to_date = date.strftime(to_date or date.today(), REQUEST_DATE_FORMAT)
        from_date = date.strftime(
            from_date or (date.today() - relativedelta(months=1)), REQUEST_DATE_FORMAT
        )
        request = {
            "tipo": "E",
            "fechaDesde": from_date,
            "fechaHasta": to_date,
        }
        return self._post_request("/services/rest/api/transferencias/listaTransferencias", request)

    def get_transfer_contacts(self):
        return self._get_request("/services/rest/api/utilidades/contactos/listado")

    def get_currencies(self):
        return self._get_request("/services/rest/api/listadivisas")
