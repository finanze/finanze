import base64
import logging
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

import httpx

from dateutil.tz import tzlocal
from domain.entity_login import (
    EntityLoginResult,
    EntitySession,
    LoginOptions,
    LoginResultCode,
)
from domain.native_entity import EntityCredentials

BASE_URL = "https://www.interactivebrokers.ie"
SESSION_LIFETIME = 50 * 60  # 50 minutes (IBKR sessions expire at ~54 min)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) "
    "Gecko/20100101 Firefox/148.0"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Referer": f"{BASE_URL}/portal/",
}


# Cookies managed by the server via Set-Cookie — must NOT be injected
# from the Electron capture to avoid conflicts with server-issued values
_SERVER_MANAGED_COOKIES = {
    "JSESSIONID",
    "x-sess-uuid",
    "PHPSESSID",
    "IS_MASTER",
    "pastandalone",
    "ROUTEIDD",
}


def _parse_cookie_string(cookie_str: str) -> dict[str, str]:
    cookies = {}
    for pair in cookie_str.split("; "):
        if "=" in pair:
            name, _, value = pair.partition("=")
            name = name.strip()
            if name and name not in cookies and name not in _SERVER_MANAGED_COOKIES:
                cookies[name] = value.strip()
    return cookies


class IBKRClient:
    def __init__(self):
        self._http: Optional[httpx.AsyncClient] = None
        self._account_id: Optional[str] = None
        self._base_currency: Optional[str] = None
        self._am_headers: Optional[dict[str, str]] = None

        self._log = logging.getLogger(__name__)

    @property
    def account_id(self) -> Optional[str]:
        return self._account_id

    @property
    def base_currency(self) -> Optional[str]:
        return self._base_currency

    async def complete_login(
        self,
        credentials: EntityCredentials,
        login_options: LoginOptions,
        session: Optional[EntitySession] = None,
    ) -> EntityLoginResult:
        logging_in = len(credentials) > 0
        if not logging_in and not self._alive_session(session):
            if login_options.avoid_new_login:
                return EntityLoginResult(code=LoginResultCode.NOT_LOGGED)
            return EntityLoginResult(code=LoginResultCode.MANUAL_LOGIN)

        now = datetime.now(tzlocal())
        if (
            session
            and not login_options.force_new_session
            and session.expiration
            and now < session.expiration
        ):
            self._init_http_client(session.payload["cookie"])
            if await self._validate_session():
                self._account_id = session.payload.get("account_id")
                self._base_currency = session.payload.get("base_currency")
                return EntityLoginResult(LoginResultCode.RESUMED)

        if not logging_in:
            return EntityLoginResult(LoginResultCode.MANUAL_LOGIN)

        try:
            self._init_http_client(credentials["cookie"])
            auth_data = await self._authenticate()
            if not auth_data:
                return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

            self._account_id = auth_data["mostRelevantAccount"]

            account_info = await self.get_accounts()
            if account_info:
                self._base_currency = account_info[0].get("currency", "EUR")

            expiration = datetime.now(tzlocal()) + timedelta(seconds=SESSION_LIFETIME)
            new_session = EntitySession(
                creation=datetime.now(tzlocal()),
                expiration=expiration,
                payload={
                    "cookie": credentials["cookie"],
                    "account_id": self._account_id,
                    "base_currency": self._base_currency,
                },
            )
            return EntityLoginResult(LoginResultCode.CREATED, session=new_session)

        except (httpx.HTTPStatusError, ValueError):
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
        except Exception as e:
            self._log.error(f"IBKR login error: {e}", exc_info=True)
            return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR)

    def _init_http_client(self, cookie_str: str):
        cookies = _parse_cookie_string(cookie_str)
        self._http = httpx.AsyncClient(
            cookies=cookies,
            headers=DEFAULT_HEADERS,
        )
        self._am_headers = None

    @staticmethod
    def _alive_session(session: Optional[EntitySession]) -> bool:
        if session is None or session.expiration is None:
            return False
        return datetime.now(tzlocal()) < session.expiration

    async def _validate_session(self) -> bool:
        try:
            await self._authenticate()
            return True
        except Exception:
            return False

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        resp = await self._http.request(method, f"{BASE_URL}{path}", **kwargs)
        if not resp.is_success:
            body = resp.text[:500] if resp.text else ""
            self._log.debug("%s %s -> %d body=%s", method, path, resp.status_code, body)
        return resp

    async def _authenticate(self) -> dict:
        resp = await self._request(
            "GET",
            "/AccountManagement/OneBarAuthentication",
            params={"json": "1"},
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "json" not in content_type:
            raise ValueError("OneBarAuthentication returned non-JSON response")
        data = resp.json()
        if "sessionId" not in data:
            raise ValueError("No sessionId in auth response")
        return data

    async def get_accounts(self) -> list[dict]:
        resp = await self._request("GET", "/portal.proxy/v1/portal/portfolio2/accounts")
        resp.raise_for_status()
        return resp.json()

    async def get_ledger(self, account_id: str) -> list[dict]:
        resp = await self._request(
            "GET", f"/portal.proxy/v1/portal/portfolio2/{account_id}/ledger"
        )
        resp.raise_for_status()
        return resp.json()

    async def get_positions(self, account_id: str) -> list[dict]:
        resp = await self._request(
            "GET", f"/portal.proxy/v1/portal/portfolio2/{account_id}/positions"
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    async def get_secdef(self, conids: list[int]) -> list[dict]:
        if not conids:
            return []
        resp = await self._request(
            "POST",
            "/portal.proxy/v1/portal/trsrv/secdef",
            json={"conids": [str(c) for c in conids], "contracts": False},
        )
        if resp.is_success:
            return resp.json().get("secdef", [])
        return []

    async def _init_am_session(self) -> bool:
        if self._am_headers:
            return True

        resp = await self._request(
            "GET",
            "/AccountManagement/AmAuthentication",
            params={"action": "Statements"},
        )
        if not resp.is_success:
            self._log.warning("AM auth failed with status %d", resp.status_code)
            return False

        html = resp.text
        match = re.search(r"var\s+AM_SESSION_ID\s*=\s*'([^']+)'", html)
        if not match:
            self._log.error("Could not find AM_SESSION_ID in AmAuthentication HTML")
            return False

        am_session_id = match.group(1)
        am_uuid = str(uuid.uuid4())
        self._am_headers = {
            "SessionId": am_session_id,
            "AM_UUID": am_uuid,
            "ACTIVE_CONTEXT": "AM_DEPENDENCY",
        }

        resp = await self._request(
            "POST",
            "/AccountManagement/Statements/PageInfo",
            json={"action": "Statements"},
            headers=self._am_headers,
        )
        if not resp.is_success:
            self._log.warning("AM PageInfo failed with status %d", resp.status_code)
            return False

        return True

    async def download_activity_statement(self, from_date: date, to_date: date) -> str:
        am_ready = await self._init_am_session()
        if not am_ready:
            self._log.error("Could not initialize AM session for statements")
            return ""

        from_str = from_date.strftime("%Y%m%d")
        to_str = to_date.strftime("%Y%m%d")

        resp = await self._request(
            "GET",
            "/AccountManagement/Statements/Run",
            headers=self._am_headers,
            params={
                "cashReportDetail": "TOTALS_WITH_SEGMENT_BREAKDOWN",
                "format": "13",
                "fromDate": from_str,
                "language": "en",
                "option": "{}",
                "period": "DATE_RANGE",
                "reportDate": to_str,
                "statementCategory": "DEFAULT_STATEMENT",
                "statementType": "DEFAULT_ACTIVITY",
                "toDate": to_str,
                "v2Modal": "true",
            },
        )
        if not resp.is_success:
            self._log.error(
                "Failed to download activity statement: %d", resp.status_code
            )
            return ""
        data = resp.json()
        file_content = data.get("fileContent", "")
        if not file_content:
            return ""
        return base64.b64decode(file_content).decode("utf-8-sig")
