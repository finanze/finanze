import json
import logging
import os
import re
from datetime import datetime, date
from typing import Optional, Union

import pyDes
import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta

from domain.login import LoginResult, LoginResultCode

REQUEST_DATE_FORMAT = "%Y-%m-%d"


class UnicajaClient:
    DEFAULT_TIMEOUT = 10

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

    def __init__(self, timeout=DEFAULT_TIMEOUT):
        self._timeout = timeout
        self._log = logging.getLogger(__name__)

    def _legacy_login(self, username: str, password: str) -> LoginResult:

        from selenium.common import TimeoutException
        from selenium.webdriver import FirefoxOptions
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
        from seleniumwire import webdriver

        driver = None

        options = FirefoxOptions()
        options.add_argument("--headless")

        wire_address = os.getenv("WIRE_ADDRESS", '127.0.0.1')
        wire_port = int(os.getenv("WIRE_PORT", "8088"))
        proxy_address = os.getenv("WIRE_PROXY_SERVER_ADDRESS", "host.docker.internal")
        webdriver_address = os.getenv("WEBDRIVER_ADDRESS", "http://localhost:4444")

        options.set_preference('network.proxy.type', 1)
        options.set_preference('network.proxy.http', proxy_address)
        options.set_preference('network.proxy.http_port', wire_port)
        options.set_preference('network.proxy.ssl', proxy_address)
        options.set_preference('network.proxy.ssl_port', wire_port)

        wire_options = {
            "auto_config": False,
            "port": wire_port,
            'addr': wire_address,
        }

        try:
            driver = webdriver.Remote(
                command_executor=webdriver_address,
                options=options,
                seleniumwire_options=wire_options
            )

            driver.get(self.BASE_URL + "/login")

            wait = WebDriverWait(driver, self._timeout)
            wait.until(EC.element_to_be_clickable((By.ID, "username")))

            username_input = driver.find_element(By.ID, "username")
            username_input.send_keys(username)

            password_input = driver.find_element(By.ID, "pwd")
            password_input.send_keys(password)

            password_input.send_keys(Keys.RETURN)

            driver.wait_for_request(self.AUTH_PATH, timeout=self._timeout)

            auth_request = next(x for x in driver.requests if self.AUTH_PATH in x.url)

            self._setup_session(auth_request)

            return LoginResult(LoginResultCode.CREATED)

        except TimeoutException:
            self._log.error("Timed out waiting for autenticacion.")
            return LoginResult(LoginResultCode.UNEXPECTED_ERROR, message="Timed out waiting for autenticacion.")

        finally:
            if driver:
                driver.quit()

    def _rest_login(self, username: str, password: str) -> LoginResult:
        user_agent = "Mozilla/5.0 (Linux; Android 5.1.1; Lenovo PB1-750M) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36"
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent

        ck = self._ck()

        abck = os.getenv("UNICAJA_ABCK")
        self._session.cookies.set("_abck", abck)

        encoded_password = self._encrypt_password(ck, password)
        auth_response = self.auth(username, encoded_password)

        if auth_response.ok:
            auth_response_body = auth_response.json()

            if "tokenCSRF" not in auth_response_body:
                return LoginResult(LoginResultCode.UNEXPECTED_ERROR, message="Token not found in response")

            self._session.headers["tokenCSRF"] = auth_response_body["tokenCSRF"]
            self._session.headers["Content-Type"] = "application/x-www-form-urlencoded"

            return LoginResult(LoginResultCode.CREATED)

        elif auth_response.status_code == 400:
            return LoginResult(LoginResultCode.INVALID_CREDENTIALS)

        else:
            return LoginResult(LoginResultCode.UNEXPECTED_ERROR,
                               message=f"Got unexpected response code {auth_response.status_code}")

    def login(self, username: str, password: str, rest_login: bool = True) -> LoginResult:
        if rest_login:
            return self._rest_login(username, password)
        else:
            return self._legacy_login(username, password)

    def _encrypt_password(self, key: str, password: str):
        return (
            pyDes.des(key, mode=pyDes.CBC, IV="00000000", pad="\0")
            .encrypt(password)
            .hex()
            .upper()
        )

    def _setup_session(self, request: requests.Request) -> dict:
        body = self._get_body(request)

        if "codigoError" in body or "mensajeError" in body:
            self._log.error("Error:", body["codigoError"], body["mensajeError"])

            if body["codigoError"] == "ERROR000":
                raise Exception("Bad credentials")

            raise Exception("There was an error during the login process")
        else:
            token_csrf = body["tokenCSRF"]
            if not token_csrf:
                raise Exception("Token CSRF not found")

        self._session = requests.Session()

        headers = {}

        headers["tokenCSRF"] = token_csrf
        headers["Cookie"] = request.headers["Cookie"]
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        self._session.headers = headers

    def _get_body(self, request: requests.Request) -> dict:
        from seleniumwire.utils import decode

        body = decode(
            request.response.body,
            request.response.headers.get("Content-Encoding", "identity"),
        )
        return json.loads(body.decode("utf-8"))

    def _execute_request(
            self,
            path: str,
            method: str,
            body: dict,
            params: dict,
            json: bool = True,
            raw: bool = False,
    ) -> Union[dict, str, requests.Response]:
        response = self._session.request(
            method, self.BASE_URL + path, data=body, params=params
        )

        if raw:
            return response

        if response.ok:
            if json:
                return response.json()
            else:
                return response.text

        self._log.error("Error Response Body: " + response.text)
        response.raise_for_status()
        return {}

    def _get_request(
            self, path: str, params: dict = None, json: bool = True
    ) -> Union[dict, str]:
        return self._execute_request(path, "GET", body=None, json=json, params=params)

    def _post_request(
            self, path: str, body: object, raw=False
    ) -> Union[dict, requests.Response]:
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
