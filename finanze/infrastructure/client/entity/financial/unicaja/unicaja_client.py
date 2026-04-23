import logging
import os
from datetime import date
from typing import Optional

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from dateutil.relativedelta import relativedelta

from domain.entity_login import EntityLoginResult, LoginResultCode
from infrastructure.client.http.http_response import HttpResponse

REQUEST_DATE_FORMAT = "%Y-%m-%d"


def _encrypt_password(key: str, password: str) -> str:
    if len(key) == 16:
        key_bytes = key.encode("utf-8")
        iv = os.urandom(16)
        encryptor = Cipher(
            algorithms.AES(key_bytes),
            modes.GCM(iv),
        ).encryptor()
        ciphertext = encryptor.update(password.encode("utf-8")) + encryptor.finalize()
        tag = encryptor.tag
        return (iv + tag + ciphertext).hex()

    if len(key) == 8:
        key_bytes = key.encode("utf-8")
        iv = b"00000000"

        password_bytes = password.encode("utf-8")
        padding_length = 8 - (len(password_bytes) % 8)
        padded_data = password_bytes + (b"\x00" * padding_length)

        cipher = Cipher(
            algorithms.TripleDES(key_bytes * 3),
            modes.CBC(iv),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        return ciphertext.hex().upper()

    raise ValueError("Unsupported key length for encryption")


def _create_mobile_client():
    from infrastructure.client.http.http_session import new_http_session

    return new_http_session()


def _create_desktop_client(retrying: bool):
    from infrastructure.client.http.http_session import new_impersonated_http_session

    browser = "chrome" if retrying else "firefox135"
    return new_impersonated_http_session(impersonate=browser)


def _create_client(mobile: bool, retrying: bool):
    if mobile:
        return _create_mobile_client()
    else:
        return _create_desktop_client(retrying)


class UnicajaClient:
    BASE_URL = "https://univia.unicajabanco.es"
    AUTH_PATH = "/services/rest/autenticacion"

    def __init__(self, use_mobile_client: bool = False):
        self._log = logging.getLogger(__name__)
        self._session = None
        self._use_mobile_client = use_mobile_client

    def _set_abck_cookie(self, abck: str) -> None:
        jar = self._session.cookies.jar
        to_delete: list[tuple[str, str]] = []
        for cookie in jar:
            if cookie.name == "_abck":
                to_delete.append((cookie.domain, cookie.path))
        for domain, path in to_delete:
            jar.clear(domain=domain, path=path)

        self._session.cookies.set(
            "_abck", abck, domain="univia.unicajabanco.es", path="/"
        )

    async def _validate_session(self) -> bool:
        try:
            response = await self._execute_request(
                "/services/rest/api/posicionGlobal/listaProductos",
                "GET",
                body=None,
                params=None,
                json=True,
                raw=True,
            )
            return response.ok
        except Exception:
            return False

    async def login(
        self, username: str, password: str, abck: str, **kwargs
    ) -> EntityLoginResult:
        if self._session and await self._validate_session():
            self._log.info("Unicaja session still alive, skipping login")
            return EntityLoginResult(LoginResultCode.RESUMED)

        if not abck:
            return EntityLoginResult(
                code=LoginResultCode.MANUAL_LOGIN,
                message="abck is required for automated login, but it was not provided",
                details={"user": username, "password": password},
            )

        retrying = kwargs.get("retrying", False)
        self._session = _create_client(self._use_mobile_client, retrying)

        ck = await self._ck()

        self._set_abck_cookie(abck)

        encoded_password = _encrypt_password(ck, password)
        auth_response = await self.auth(username, encoded_password)

        if auth_response.ok:
            auth_response_body = await auth_response.json()

            if "tokenCSRF" not in auth_response_body:
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Token not found in response",
                )

            self._session.headers["tokenCSRF"] = auth_response_body["tokenCSRF"]
            self._session.headers["Content-Type"] = "application/x-www-form-urlencoded"

            return EntityLoginResult(LoginResultCode.CREATED)

        elif auth_response.status == 400:
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

        elif auth_response.status == 403:
            if not retrying and not self._use_mobile_client:
                self._log.error(
                    "Login failed with 403, retrying with different browser impersonation..."
                )
                return await self.login(username, password, abck, retrying=True)

            return EntityLoginResult(
                LoginResultCode.MANUAL_LOGIN,
                message="abck may not be valid anymore",
                details={"user": username, "password": password},
            )

        else:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected response code {auth_response.status}",
            )

    async def _execute_request(
        self,
        path: str,
        method: str,
        body: dict,
        params: dict,
        json: bool = True,
        raw: bool = False,
    ) -> dict | str | HttpResponse:
        response = await self._session.request(
            method, self.BASE_URL + path, data=body, params=params
        )

        if raw:
            return response

        if response.ok:
            if json:
                return await response.json()
            else:
                return (await response.read()).decode("windows-1252")

        self._log.error("Error Response Body: " + await response.text())
        response.raise_for_status()
        return {}

    async def _get_request(
        self, path: str, params: dict = None, json: bool = True
    ) -> dict | str:
        return await self._execute_request(
            path, "GET", body=None, json=json, params=params
        )

    async def _post_request(
        self, path: str, body: object, raw=False
    ) -> dict | HttpResponse:
        return await self._execute_request(
            path, "POST", body=body, json=True, raw=raw, params=None
        )

    async def _ck(self):
        return (await self._get_request("/services/rest/openapi/ckLogin"))[
            "ck"
        ]  # /services/rest/openapi/v2/ck

    async def auth(self, username: str, encoded_password: str):
        data = {
            "idioma": "es",
            "usuario": username,
            "password": encoded_password,
            "origen": "bdigital",
        }
        return await self._post_request(self.AUTH_PATH, body=data, raw=True)

    async def get_user(self):
        return await self._get_request("/services/rest/perfilusuario")

    async def list_accounts(self):
        return await self._get_request("/services/rest/api/productos/listacuentas")

    async def get_account_movements(self, ppp: str):
        # account_movs_request = {"ppp": ppp, "indOperacion": "I"}
        account_movs_request = {
            "ppp": ppp,
            "saldoUltMov": "283.57",
            "numUltMov": "1097",
            "indOperacion": "P",
        }
        return await self._post_request(
            "/services/rest/api/cuentas/listadoMovimientos", account_movs_request
        )

    async def get_account_movement(self, ppp: str, nummov: str):
        return await self._get_request(
            f"/services/rest/api/cuentas/movimientos/detallemovimiento?ppp={ppp}&nummov={nummov}"
        )

    async def get_cards(self):
        return await self._get_request("/services/rest/api/productos/listatarjetas")

    async def get_card(self, ppp: str, card_type: str):
        card_details_request = {"ppp": ppp, "tipotarjeta": card_type}
        return await self._post_request(
            "/services/rest/api/tarjetas/detalleTarjeta", card_details_request
        )

    async def get_card_config(self, ppp: str):
        card_config_request = {"ppp": ppp}
        return await self._post_request(
            "/services/rest/api/tarjetas/configuracionUso/datos", card_config_request
        )

    async def get_card_movements(self, ppp: str, from_date: Optional[date] = None):
        from_date = date.strftime(
            from_date or (date.today() - relativedelta(months=1)), REQUEST_DATE_FORMAT
        )
        card_movs_request = {"ppp": ppp, "fechaDesde": from_date, "impDesde": "0"}
        return await self._post_request(
            "/services/rest/api/tarjetas/movimientos/listadoMovimientos/v2",
            card_movs_request,
        )

    async def get_loans(self):
        return await self._get_request("/services/rest/api/productos/listaprestamos")

    async def get_loan(self, ppp: str):
        loan_request = {"ppp": ppp}
        return await self._post_request(
            "/services/rest/api/prestamos/consultaPrestamo", loan_request
        )

    async def get_loan_movements(self, ppp: str):
        request = {"ppp": ppp}
        return await self._post_request(
            "/services/rest/api/prestamos/listadoMovimientos", request
        )

    async def get_transfers_summary(self):
        return await self._get_request("/services/rest/api/transferencias/resumen")

    async def get_transfers_historic(
        self, from_date: Optional[date] = None, to_date: Optional[date] = None
    ):
        to_date = date.strftime(to_date or date.today(), REQUEST_DATE_FORMAT)
        from_date = date.strftime(
            from_date or (date.today() - relativedelta(months=1)), REQUEST_DATE_FORMAT
        )
        request = {
            "tipo": "E",
            "fechaDesde": from_date,
            "fechaHasta": to_date,
        }
        return await self._post_request(
            "/services/rest/api/transferencias/listaTransferencias", request
        )

    async def get_transfer_contacts(self):
        return await self._get_request(
            "/services/rest/api/utilidades/contactos/listado"
        )

    async def get_currencies(self):
        return await self._get_request("/services/rest/api/listadivisas")

    async def get_products_summary(self):
        return await self._get_request(
            "/services/rest/api/posicionGlobal/listaProductos"
        )

    async def list_fund_accounts(self):
        return await self._get_request(
            "/services/rest/api/productos/listacuentasfondos"
        )

    async def get_periodic_subscriptions(self, account):
        await self._get_request("/services/rest/api/fondos/consulta?cuenta=" + account)
        request = {"opcion": "D"}
        return await self._post_request(
            "/services/rest/api/fondos/listaSuscripcionesPeriodicas", request
        )
