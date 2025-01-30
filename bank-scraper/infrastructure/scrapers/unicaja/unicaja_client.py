import json
import os
import re
from datetime import datetime, date
from typing import Optional, Union

import pyDes
import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta

from domain.scrap_result import LoginResult

REQUEST_DATE_FORMAT = "%Y-%m-%d"


class UnicajaClient:
    DEFAULT_TIMEOUT = 10

    BASE_URL = "https://univia.unicajabanco.es"
    AUTH_PATH = "/services/rest/autenticacion"

    loan_key_mapping = {
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
        self.__timeout = timeout

    def legacy_login(self, username: str, password: str) -> dict:

        from seleniumwire import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.keys import Keys

        geckodriver_path = os.getenv("GECKODRIVER_PATH")

        driver = None
        try:
            options = Options()
            service = None
            if geckodriver_path:
                service = Service(executable_path=geckodriver_path)
            options.add_argument("--headless")
            driver = webdriver.Firefox(options=options, service=service)

            driver.get(self.BASE_URL + "/login")

            wait = WebDriverWait(driver, self.__timeout)
            wait.until(EC.element_to_be_clickable((By.ID, "username")))

            username_input = driver.find_element(By.ID, "username")
            username_input.send_keys(username)

            password_input = driver.find_element(By.ID, "pwd")
            password_input.send_keys(password)

            password_input.send_keys(Keys.RETURN)

            driver.wait_for_request(self.AUTH_PATH, timeout=self.__timeout)

            auth_request = next(x for x in driver.requests if self.AUTH_PATH in x.url)

            self.__setup_session(auth_request)

            return {"result": LoginResult.CREATED}

        except TimeoutException:
            print("Timed out waiting for autenticacion.")

        finally:
            if driver:
                driver.quit()

    def rest_login(self, username: str, password: str) -> dict:
        user_agent = "Mozilla/5.0 (Linux; Android 5.1.1; Lenovo PB1-750M) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36"
        self.__session = requests.Session()
        self.__session.headers["User-Agent"] = user_agent

        ck = self.ck()

        abck = os.getenv("UNICAJA_ABCK")
        self.__session.cookies.set("_abck", abck)

        encoded_password = self.__encrypt_password(ck, password)
        auth_response = self.auth(username, encoded_password)

        if auth_response.ok:
            auth_response_body = auth_response.json()

            if "tokenCSRF" not in auth_response_body:
                return {"result": LoginResult.UNEXPECTED_ERROR, "message": "Token not found in response"}

            self.__session.headers["tokenCSRF"] = auth_response_body["tokenCSRF"]
            self.__session.headers["Content-Type"] = "application/x-www-form-urlencoded"

            return {"result": LoginResult.CREATED}

        elif auth_response.status_code == 400:
            return {"result": LoginResult.INVALID_CREDENTIALS}

        else:
            return {"result": LoginResult.UNEXPECTED_ERROR,
                    "message": f"Got unexpected response code {auth_response.status_code}"}

    def login(self, username: str, password: str, rest_login: bool = True) -> dict:
        if rest_login:
            return self.rest_login(username, password)
        else:
            return self.legacy_login(username, password)

    def __encrypt_password(self, key: str, password: str):
        return (
            pyDes.des(key, mode=pyDes.CBC, IV="00000000", pad="\0")
            .encrypt(password)
            .hex()
            .upper()
        )

    def __setup_session(self, request: requests.Request) -> dict:
        body = self.__get_body(request)

        if "codigoError" in body or "mensajeError" in body:
            print("Error:", body["codigoError"], body["mensajeError"])

            if body["codigoError"] == "ERROR000":
                raise Exception("Bad credentials")

            raise Exception("There was an error during the login process")
        else:
            tokenCsrf = body["tokenCSRF"]
            if not tokenCsrf:
                raise Exception("Token CSRF not found")

        self.__session = requests.Session()

        headers = {}

        headers["tokenCSRF"] = tokenCsrf
        headers["Cookie"] = request.headers["Cookie"]
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        self.__session.headers = headers

    def __get_body(self, request: requests.Request) -> dict:
        from seleniumwire.utils import decode

        body = decode(
            request.response.body,
            request.response.headers.get("Content-Encoding", "identity"),
        )
        return json.loads(body.decode("utf-8"))

    def __execute_request(
            self,
            path: str,
            method: str,
            body: dict,
            params: dict,
            json: bool = True,
            raw: bool = False,
    ) -> Union[dict, str, requests.Response]:
        response = self.__session.request(
            method, self.BASE_URL + path, data=body, params=params
        )

        if raw:
            return response

        if response.ok:
            if json:
                return response.json()
            else:
                return response.text

        print("Error Status Code:", response.status_code)
        print("Error Response Body:", response.text)
        raise Exception("There was an error during the request")

    def __get_request(
            self, path: str, params: dict = None, json: bool = True
    ) -> Union[dict, str]:
        return self.__execute_request(path, "GET", body=None, json=json, params=params)

    def __post_request(
            self, path: str, body: object, raw=False
    ) -> Union[dict, requests.Response]:
        return self.__execute_request(path, "POST", body=body, json=True, raw=raw, params=None)

    def ck(self):
        return self.__get_request("/services/rest/openapi/ck")["ck"]

    def auth(self, username: str, encoded_password: str):
        data = {
            "idioma": "es",
            "usuario": username,
            "password": encoded_password,
            "origen": "bdigital",
        }
        return self.__post_request(self.AUTH_PATH, body=data, raw=True)

    def get_user(self):
        return self.__get_request("/services/rest/perfilusuario")

    def list_accounts(self):
        return self.__get_request("/services/rest/api/productos/listacuentas")

    def get_account_movements(self):
        account_movs_request = {"ppp": "003", "indOperacion": "I"}
        account_movs_request = {
            "ppp": "003",
            "saldoUltMov": "283.57",
            "numUltMov": "1097",
            "indOperacion": "P",
        }
        return self.__post_request(
            "/services/rest/api/cuentas/listadoMovimientos", account_movs_request
        )

    def get_account_movement(self, ppp: str, nummov: str):
        # ppp=003&nummov=000001037
        return self.__get_request(
            f"/services/rest/api/cuentas/movimientos/detallemovimiento?ppp={ppp}&nummov={nummov}"
        )

    def get_cards(self):
        return self.__get_request("/services/rest/api/productos/listatarjetas")

    def get_card(self):
        card_details_request = {"ppp": "002", "tipotarjeta": "2"}
        return self.__post_request(
            "/services/rest/api/tarjetas/detalleTarjeta", card_details_request
        )

    def get_card_config(self):
        card_config_request = {"ppp": "002"}
        return self.__post_request(
            "/services/rest/api/tarjetas/configuracionUso/datos", card_config_request
        )

    def get_card_movements(self, from_date: Optional[date] = None):
        from_date = date.strftime(
            from_date or (date.today() - relativedelta(months=1)), REQUEST_DATE_FORMAT
        )
        card_movs_request = {"ppp": "002", "fechaDesde": from_date, "impDesde": "0"}
        return self.__post_request(
            "/services/rest/api/tarjetas/movimientos/listadoMovimientos/v2",
            card_movs_request,
        )

    def get_loans(self):
        return self.__get_request("/services/rest/api/productos/listaprestamos")

    def get_loan(self, p: str, ppp: str):
        loan_request = {"o": "dpres", "p": p, "ppp": ppp}
        response = self.__get_request(
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

                    english_key = self.loan_key_mapping.get(spanish_key)

                    if english_key:
                        loan_data[english_key] = format_value(value)

        return loan_data

    def get_transfers_summary(self):
        return self.__get_request("/services/rest/api/transferencias/resumen")

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
        return self.__post_request("/services/rest/api/transferencias/listaTransferencias", request)

    def get_transfer_contacts(self):
        return self.__get_request("/services/rest/api/utilidades/contactos/listado")

    def get_currencies(self):
        return self.__get_request("/services/rest/api/listadivisas")
