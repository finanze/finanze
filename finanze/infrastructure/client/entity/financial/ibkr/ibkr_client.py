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

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
# Account Management pages are noticeably slower than the portal API
AM_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
# Statements are generated on demand by IBKR and can take minutes to build
STATEMENT_TIMEOUT = httpx.Timeout(180.0, connect=10.0)

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


class IBKRStatementError(Exception):
    """Raised when an activity statement cannot be retrieved from IBKR."""


def _parse_cookie_string(cookie_str: str) -> dict[str, str]:
    cookies = {}
    for pair in cookie_str.split("; "):
        if "=" in pair:
            name, _, value = pair.partition("=")
            name = name.strip()
            if name and name not in cookies and name not in _SERVER_MANAGED_COOKIES:
                cookies[name] = value.strip()
    return cookies


def _is_json(resp: httpx.Response) -> bool:
    return "json" in resp.headers.get("content-type", "")


def _statement_error(resp: httpx.Response) -> Optional[str]:
    # IBKR's own error for a period it cannot produce a statement for
    if not _is_json(resp):
        return None
    try:
        return resp.json().get("errors", {}).get("stmtError")
    except ValueError:
        return None


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
        logging_in = "cookie" in credentials
        if not logging_in and not self._alive_session(session):
            if login_options.avoid_new_login:
                return EntityLoginResult(code=LoginResultCode.NOT_LOGGED)
            return EntityLoginResult(
                code=LoginResultCode.MANUAL_LOGIN, details=credentials
            )

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
            return EntityLoginResult(LoginResultCode.MANUAL_LOGIN, details=credentials)

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
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )
        self._am_headers = None

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None
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
            timeout=AM_TIMEOUT,
        )
        if not resp.is_success:
            self._log.warning("AM auth failed with status %d", resp.status_code)
            return False

        html = resp.text
        match = re.search(r"var\s+AM_SESSION_ID\s*=\s*'([^']+)'", html)
        if not match:
            self._log.error("Could not find AM_SESSION_ID in AmAuthentication HTML")
            return False

        am_headers = {
            "SessionId": match.group(1),
            "AM_UUID": str(uuid.uuid4()),
            "ACTIVE_CONTEXT": "AM_DEPENDENCY",
            "Accept": "application/json, text/plain, */*",
        }

        resp = await self._request(
            "POST",
            "/AccountManagement/Statements/PageInfo",
            json={"action": "Statements"},
            headers=am_headers,
            timeout=AM_TIMEOUT,
        )
        if not resp.is_success:
            self._log.warning("AM PageInfo failed with status %d", resp.status_code)
            return False

        # Statements are run against the account picked in the AM session, which
        # is identified by a hash. Without it IBKR answers 200 with an empty body
        account_hash = self._account_hash_from_page_info(resp)
        if account_hash is None:
            self._log.error("No account selection found in Statements PageInfo")
            return False
        am_headers["AccountHash"] = str(account_hash)

        self._am_headers = am_headers
        return True

    def _account_hash_from_page_info(self, resp: httpx.Response) -> Optional[int]:
        try:
            selections = resp.json().get("picker", {}).get("activeSelections", [])
        except ValueError:
            return None

        for selection in selections:
            if selection.get("accountId") == self._account_id:
                return selection.get("id")
        return selections[0].get("id") if selections else None

    async def _run_statement(self, from_str: str, to_str: str) -> httpx.Response:
        if not await self._init_am_session():
            raise IBKRStatementError("Could not initialize AM session for statements")

        return await self._request(
            "GET",
            "/AccountManagement/Statements/Run",
            headers=self._am_headers,
            timeout=STATEMENT_TIMEOUT,
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

    async def download_activity_statement(self, from_date: date, to_date: date) -> str:
        from_str = from_date.strftime("%Y%m%d")
        to_str = to_date.strftime("%Y%m%d")

        resp = await self._run_statement(from_str, to_str)
        if not _is_json(resp):
            # Both the statement and IBKR's own errors come back as JSON, so
            # anything else means the AM session went stale: rebuild and retry
            self._log.warning(
                "Unexpected statement response (%d, %s), retrying with a new AM session",
                resp.status_code,
                resp.headers.get("content-type", ""),
            )
            self._am_headers = None
            resp = await self._run_statement(from_str, to_str)

        error = _statement_error(resp)
        if error:
            # No activity in that period, or a range the account cannot report on
            self._log.info("No statement for %s-%s: %s", from_str, to_str, error)
            return ""

        if not resp.is_success:
            raise IBKRStatementError(
                f"Statement request failed with status {resp.status_code}"
            )

        if not _is_json(resp):
            self._log.error("Unexpected statement response body: %s", resp.text[:500])
            raise IBKRStatementError("Statement request returned a non-JSON response")

        file_content = resp.json().get("fileContent", "")
        if not file_content:
            self._log.warning(
                "Empty statement returned for range %s-%s", from_str, to_str
            )
            return ""
        return base64.b64decode(file_content).decode("utf-8-sig")
