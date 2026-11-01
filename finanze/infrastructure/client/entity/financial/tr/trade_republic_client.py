import asyncio
import base64
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

import httpx
from aiocache import cached
from dateutil.tz import tzlocal
from tzlocal import get_localzone

from domain.entity_login import (
    EntityLoginResult,
    EntitySession,
    LoginConfirmationType,
    LoginOptions,
    LoginResultCode,
)
from infrastructure.client.entity.financial.tr.api import TradeRepublicApi
from infrastructure.client.entity.financial.tr.portfolio import Portfolio
from infrastructure.client.entity.financial.tr.tr_details import TRDetails
from infrastructure.client.entity.financial.tr.tr_timeline import TRTimeline
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.client.http.http_session import get_http_session


class _TradeRepublicAuthLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "api.traderepublic.com" in message:
            redacted = re.sub(
                r"(https://api\.traderepublic\.com/api/v[12]/auth/web/login/)[^\s\"?]+",
                r"\1[REDACTED]",
                message,
            )
            if redacted != message:
                record.msg = redacted
                record.args = ()
        return True


_TR_AUTH_LOG_FILTER = _TradeRepublicAuthLogFilter()


def _json_cookie_jar(jar: httpx.Cookies) -> list[dict]:
    simple_cookies: list[dict] = []
    for cookie in jar.jar:
        expires_timestamp = 0
        if cookie.expires is not None:
            try:
                expires_timestamp = int(cookie.expires)
            except (ValueError, TypeError):
                expires_timestamp = 0

        cookie_dict = {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "expires": expires_timestamp,
            "secure": cookie.secure,
        }
        simple_cookies.append(cookie_dict)

    return simple_cookies


def _rebuild_cookie_jar(cookie_list: list[dict]) -> httpx.Cookies:
    cookies = httpx.Cookies()

    for cookie_dict in cookie_list:
        if not all(k in cookie_dict for k in ("name", "value", "domain")):
            continue

        name = cookie_dict["name"]
        value = cookie_dict["value"]
        domain = cookie_dict["domain"]
        path = cookie_dict.get("path") or "/"

        cookies.set(
            name,
            value,
            domain=domain,
            path=path,
        )

    return cookies


class TradeRepublicClient:
    IN_APP_POLL_INTERVAL = 3
    IN_APP_TIMEOUT_SECONDS = 120
    AUTHENTICATOR_CODE_LENGTH = 6
    _V2_HEADERS = {
        "x-tr-platform": "web",
    }
    _APP_VERSION_URL = "https://app.traderepublic.com/app-version.txt"
    _DEFAULT_APP_VERSION = "15.7.0"

    def __init__(self):
        self._tr_api = None
        self._log = logging.getLogger(__name__)
        logging.getLogger("httpx").addFilter(_TR_AUTH_LOG_FILTER)
        self._cancel_event: asyncio.Event = asyncio.Event()
        self._stable_device_id: str | None = None
        self._v1_header_process_id: str | None = None
        self._v2_deadline: datetime | None = None
        self._v2_authenticator_required = False
        self._v2_authenticator_verified = False

    def _log_login_error(
        self, stage: str, status: int, body: str, extra_secrets: tuple[str, ...] = ()
    ) -> None:
        secrets: list[str | None] = list(extra_secrets)
        if self._tr_api:
            secrets.extend(
                [
                    self._tr_api.phone_no,
                    self._tr_api.pin,
                    self._tr_api._process_id,
                    self._tr_api._websession.headers.get("x-aws-waf-token"),
                ]
            )
            secrets.extend(
                cookie.value for cookie in self._tr_api._websession.cookie_jar
            )

        def redact(value: str) -> str:
            for secret in secrets:
                if isinstance(secret, str) and secret:
                    value = value.replace(secret, "[REDACTED]")
            value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED]", value)
            value = re.sub(r"(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)", "[REDACTED]", value)
            value = re.sub(r"(?<!\w)\d{4,8}(?!\w)", "[REDACTED]", value)
            value = re.sub(
                r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
                "[REDACTED]",
                value,
            )
            return value[:512]

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            response = f"<non-JSON body omitted; length={len(body)}>"
        else:
            safe: dict[str, object] = {}
            if isinstance(payload, dict):
                for key in ("errorCode", "errorMessage", "message"):
                    if isinstance(payload.get(key), str):
                        safe[key] = redact(payload[key])
                errors = payload.get("errors")
                if isinstance(errors, list):
                    safe_errors: list[dict[str, object]] = []
                    for error in errors[:5]:
                        if not isinstance(error, dict):
                            continue
                        safe_error: dict[str, object] = {
                            key: redact(error[key])
                            for key in ("errorCode", "errorMessage")
                            if isinstance(error.get(key), str)
                        }
                        meta = error.get("meta")
                        if isinstance(meta, dict):
                            safe_meta: dict[str, object] = {
                                key: redact(meta[key])
                                for key in (
                                    "field",
                                    "reason",
                                    "errorType",
                                    "header",
                                    "headerName",
                                    "missingHeader",
                                    "requiredHeader",
                                )
                                if isinstance(meta.get(key), str)
                            }
                            for key in ("nextAttemptInSeconds", "retryAfter"):
                                if isinstance(meta.get(key), int):
                                    safe_meta[key] = meta[key]
                            for key in ("missingHeaders", "requiredHeaders"):
                                values = meta.get(key)
                                if isinstance(values, list):
                                    safe_meta[key] = [
                                        redact(value)
                                        for value in values[:10]
                                        if isinstance(value, str)
                                    ]
                            if safe_meta:
                                safe_error["meta"] = safe_meta
                        safe_errors.append(safe_error)
                    safe["errors"] = safe_errors
            response = json.dumps(safe, ensure_ascii=True)[:2048]
        self._log.error(
            "Trade Republic %s failed: status=%s response=%s", stage, status, response
        )

    @staticmethod
    def _first_login_error(body: str) -> dict:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, dict):
            return {}
        errors = payload.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            return errors[0]
        return payload

    def _cooldown_result(self, error: dict) -> EntityLoginResult:
        meta = error.get("meta")
        wait = meta.get("nextAttemptInSeconds", 60) if isinstance(meta, dict) else 60
        if not isinstance(wait, int) or isinstance(wait, bool) or wait < 0:
            self._log.warning("Trade Republic returned an invalid cooldown duration")
            wait = 60
        return EntityLoginResult(
            LoginResultCode.COOLDOWN,
            message=f"Too many attempts, wait {wait} seconds before retrying",
            details={"wait": wait},
        )

    @staticmethod
    def _generate_stable_device_id() -> str:
        return hashlib.sha512(os.urandom(64)).hexdigest()

    def _build_device_info_header(self) -> str:
        now = datetime.now(tzlocal())
        utc_offset_minutes = int(now.utcoffset().total_seconds() // 60)
        device_info = {
            "stableDeviceId": self._stable_device_id,
            "model": "Apple Macintosh",
            "browser": "Firefox",
            "browserVersion": "138.0",
            "os": "Mac OS",
            "osVersion": "10.15",
            "timezone": self._get_timezone(),
            "timezoneOffset": -utc_offset_minutes,
            "screen": "2560x1440x24",
            "preferredLanguages": ["en-US", "en"],
            "numberOfCores": 4,
        }
        return base64.b64encode(
            json.dumps(device_info, separators=(",", ":")).encode()
        ).decode()

    @staticmethod
    def _get_timezone() -> str:
        try:
            import js

            return str(js.Intl.DateTimeFormat().resolvedOptions().timeZone)
        except Exception:
            return str(get_localzone())

    async def _get_v2_headers(self) -> dict:
        app_version = await self._fetch_app_version()
        return {
            **self._V2_HEADERS,
            "x-tr-app-version": app_version,
            "x-tr-device-info": self._build_device_info_header(),
        }

    @cached(ttl=86400, noself=True)
    async def _fetch_app_version(self) -> str:
        try:
            session = get_http_session()
            r = await session.get(self._APP_VERSION_URL)
            r.raise_for_status()
            version = (await r.text()).strip()
            if version:
                return version
        except Exception:
            self._log.warning("Failed to fetch TR app version, using default")
        return self._DEFAULT_APP_VERSION

    async def login(
        self,
        phone: str,
        pin: str,
        login_options: LoginOptions,
        process_id: str = None,
        code: str = None,
        waf_token: str = None,
        session: Optional[EntitySession] = None,
        use_v2: bool = False,
    ) -> EntityLoginResult:
        if not phone.startswith("+"):
            return EntityLoginResult(
                LoginResultCode.INVALID_CREDENTIALS,
                message="Phone number must start with international prefix (like +34)",
            )

        if (
            not use_v2
            and code
            and process_id
            and self._v1_header_process_id is not None
        ):
            api = self._tr_api
            if (
                process_id != self._v1_header_process_id
                or not api
                or api._process_id != process_id
            ):
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Login process is no longer active",
                )
            if api.phone_no != phone or api.pin != pin:
                return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
            if self._cancel_event.is_set():
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Login cancelled by user.",
                )
            return await self._complete_v1_login(process_id, code, waf_token)

        self._cancel_event.clear()
        self._v1_header_process_id = None
        self._v2_deadline = None
        self._v2_authenticator_required = False
        self._v2_authenticator_verified = False
        self._tr_api = TradeRepublicApi(
            phone_no=phone,
            pin=pin,
            locale="en",
        )

        if session and not login_options.force_new_session:
            self._inject_session(session)
            resume_result = await self._resumable_session()
            if resume_result:
                self._log.debug("Resuming session")
                return EntityLoginResult(resume_result)

        if waf_token:
            self._tr_api._websession.headers["x-aws-waf-token"] = waf_token
        else:
            return EntityLoginResult(
                LoginResultCode.MANUAL_LOGIN,
                details={"phone": phone, "password": pin},
            )

        if not self._stable_device_id:
            self._stable_device_id = self._generate_stable_device_id()

        if code and process_id:
            return await self._complete_v1_login(process_id, code, waf_token)

        elif not code or not process_id:
            if not login_options.avoid_new_login:
                if use_v2:
                    return await self._login_v2()
                else:
                    return await self._login_v1()
            else:
                return EntityLoginResult(LoginResultCode.NOT_LOGGED)

        return EntityLoginResult(
            LoginResultCode.UNEXPECTED_ERROR,
            message="Unexpected behavior during login",
        )

    async def _complete_v1_login(
        self, process_id: str, code: str, waf_token: str | None
    ) -> EntityLoginResult:
        api = self._tr_api
        api._process_id = process_id
        try:
            await api.complete_weblogin(code)
        except httpx.HTTPStatusError as e:
            if self._tr_api is not api:
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Login process is no longer active",
                )
            self._log_login_error(
                "v1 verification", e.response.status_code, e.response.text, (code,)
            )
            error_code = self._first_login_error(e.response.text).get("errorCode")
            if e.response.status_code == 401:
                return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
            if e.response.status_code == 400:
                if error_code == "MISSING_REQUIRED_HEADER":
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR,
                        message="Trade Republic requires an additional login header",
                    )
                return EntityLoginResult(LoginResultCode.INVALID_CODE)
            if e.response.status_code == 403:
                return EntityLoginResult(LoginResultCode.CURRENTLY_UNAVAILABLE)
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected error {e.response.status_code} during login",
            )

        if self._tr_api is not api or self._cancel_event.is_set():
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="Login process is no longer active",
            )
        self._v1_header_process_id = None
        token = api._websession.headers.get("x-aws-waf-token") or waf_token
        session_payload = self._export_session(token)
        new_session = EntitySession(
            creation=datetime.now(tzlocal()), expiration=None, payload=session_payload
        )
        return EntityLoginResult(LoginResultCode.CREATED, session=new_session)

    async def _login_v1(self) -> EntityLoginResult:
        retried_with_headers = False
        while True:
            try:
                result = await self._initiate_weblogin()
                if isinstance(result, EntityLoginResult):
                    return result
                if retried_with_headers:
                    if not self._tr_api._process_id:
                        self._log.error(
                            "Trade Republic v1 retry returned an empty process ID"
                        )
                        return EntityLoginResult(
                            LoginResultCode.UNEXPECTED_ERROR,
                            message="processId not in response",
                        )
                    self._v1_header_process_id = self._tr_api._process_id
                return EntityLoginResult(
                    LoginResultCode.CODE_REQUESTED,
                    process_id=self._tr_api._process_id,
                    details={"wait": result},
                )
            except httpx.HTTPStatusError as e:
                self._log_login_error(
                    "v1 login", e.response.status_code, e.response.text
                )
                error = self._first_login_error(e.response.text)
                if (
                    not retried_with_headers
                    and e.response.status_code == 400
                    and error.get("errorCode") == "MISSING_REQUIRED_HEADER"
                ):
                    api = self._tr_api
                    headers = await self._get_v2_headers()
                    if self._tr_api is not api or self._cancel_event.is_set():
                        return EntityLoginResult(
                            LoginResultCode.UNEXPECTED_ERROR,
                            message="Login process is no longer active",
                        )
                    api._websession.headers.update(
                        {**headers, "accept-language": api._locale}
                    )
                    retried_with_headers = True
                    self._log.info(
                        "Retrying Trade Republic v1 login with device headers"
                    )
                    continue
                if e.response.status_code in (403, 405):
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR,
                        message="Invalid challenge token",
                    )
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Got unexpected error {e.response.status_code} during login, {e.response.text}",
                )
            except ValueError as e:
                if str(e) == "NUMBER_INVALID":
                    return EntityLoginResult(
                        LoginResultCode.INVALID_CREDENTIALS,
                        message="Invalid phone number, maybe missing international prefix",
                    )
                raise

    async def _login_v2(self) -> EntityLoginResult:
        try:
            result = await self._initiate_weblogin_v2()
            if isinstance(result, EntityLoginResult):
                return result
            else:
                process_id = result

        except httpx.HTTPStatusError as e:
            self._log_login_error("v2 login", e.response.status_code, e.response.text)
            if e.response.status_code in (403, 405):
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Invalid challenge token",
                )
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Got unexpected error {e.response.status_code} during login, {e.response.text}",
            )

        except ValueError as e:
            if str(e) == "NUMBER_INVALID":
                return EntityLoginResult(
                    LoginResultCode.INVALID_CREDENTIALS,
                    message="Invalid phone number, maybe missing international prefix",
                )
            raise

        return EntityLoginResult(
            LoginResultCode.CODE_REQUESTED,
            confirmation_type=LoginConfirmationType.IN_APP,
            process_id=process_id,
        )

    def cancel_login(self) -> None:
        self._cancel_event.set()

    async def complete_login(
        self, process_id: str, waf_token: str, code: str | None = None
    ) -> EntityLoginResult:
        if not self._tr_api:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="No login in progress",
            )
        if self._tr_api._process_id != process_id:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="Login process is no longer active",
            )
        if self._cancel_event.is_set():
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="Login cancelled by user.",
            )

        if not self._stable_device_id:
            self._stable_device_id = self._generate_stable_device_id()

        if code is not None:
            return await self._verify_authenticator(process_id, code)

        result = await self._poll_weblogin_v2(process_id)
        if result is not None:
            return result

        self._tr_api._weblogin = True
        sess_created_at = datetime.now(tzlocal())
        token = waf_token or self._tr_api._websession.headers.get("x-aws-waf-token")
        session_payload = self._export_session(token)
        new_session = EntitySession(
            creation=sess_created_at, expiration=None, payload=session_payload
        )
        return EntityLoginResult(LoginResultCode.CREATED, session=new_session)

    async def _resumable_session(self) -> LoginResultCode | None:
        try:
            await self._tr_api.settings()
        except httpx.HTTPStatusError:
            self._tr_api._weblogin = False
            return None

        if not await self._tr_api.has_websocket_auth():
            self._tr_api._weblogin = False
            self._log.info("Stored session has no Trade Republic websocket token")
            return LoginResultCode.LOGIN_REQUIRED

        return LoginResultCode.RESUMED

    async def _parse_login_response(
        self, r: HttpResponse, stage: str
    ) -> dict | EntityLoginResult:
        try:
            j = await r.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            if r.status == 429:
                self._log_login_error(stage, r.status, await r.text())
                return self._cooldown_result({})
            r.raise_for_status()
            self._log.error("Trade Republic %s returned invalid JSON", stage)
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR, message="Invalid login response"
            )
        if not isinstance(j, dict):
            if r.status == 429:
                self._log_login_error(stage, r.status, await r.text())
                return self._cooldown_result({})
            r.raise_for_status()
            self._log.error("Trade Republic %s returned an invalid response", stage)
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR, message="Invalid login response"
            )

        errs = j.get("errors")
        err = {}
        if isinstance(errs, list) and errs and isinstance(errs[0], dict):
            err = errs[0]
        try:
            if (
                r.status == 429
                or errs
                and err
                and err.get("errorCode") == "TOO_MANY_REQUESTS"
            ):
                self._log_login_error(stage, r.status, await r.text())
                return self._cooldown_result(err)

            elif errs and err and err.get("errorCode"):
                if r.status < 400:
                    self._log_login_error(stage, r.status, await r.text())
                r.raise_for_status()
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Got a unexpected error during login, {err.get('errorMessage')}",
                )
            elif errs:
                r.raise_for_status()
                self._log_login_error(stage, r.status, await r.text())
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR, message="Invalid login response"
                )

            self._tr_api._process_id = j["processId"]

        except KeyError:
            r.raise_for_status()
            self._log.error("Trade Republic %s returned no process ID", stage)
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="processId not in response",
            )

        r.raise_for_status()
        return j

    async def _initiate_weblogin(self) -> int | EntityLoginResult:
        api = self._tr_api
        r = await api._websession.post(
            f"{api._host}/api/v1/auth/web/login",
            json={"phoneNumber": api.phone_no, "pin": api.pin},
        )
        if self._tr_api is not api:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="Login process is no longer active",
            )
        result = await self._parse_login_response(r, "v1 login")
        if isinstance(result, EntityLoginResult):
            return result
        return int(result.get("countdownInSeconds", 0)) + 1

    async def _initiate_weblogin_v2(self) -> str | EntityLoginResult:
        api = self._tr_api
        r = await api._websession.post(
            f"{api._host}/api/v2/auth/web/login",
            json={"phoneNumber": api.phone_no, "pin": api.pin},
            headers=await self._get_v2_headers(),
        )
        if self._tr_api is not api:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="Login process is no longer active",
            )
        result = await self._parse_login_response(r, "v2 login")
        if isinstance(result, EntityLoginResult):
            return result
        if not self._tr_api._process_id:
            self._log.error("Trade Republic v2 login returned an empty process ID")
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR, message="processId not in response"
            )
        return self._tr_api._process_id

    async def _verify_authenticator(
        self, process_id: str, code: str
    ) -> EntityLoginResult:
        if not self._v2_authenticator_required or self._v2_authenticator_verified:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="No authenticator verification is pending",
            )
        if self._v2_deadline and datetime.now(tzlocal()) >= self._v2_deadline:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="In-app confirmation timed out. Please try again.",
            )

        api = self._tr_api
        r = await api._websession.post(
            f"{api._host}/api/v2/auth/web/login/processes/{process_id}/authenticator-verification",
            json={"code": code},
            headers=await self._get_v2_headers(),
        )
        if self._tr_api is not api or self._cancel_event.is_set():
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="Login process is no longer active",
            )
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._log_login_error(
                "v2 authenticator verification",
                e.response.status_code,
                e.response.text,
                (process_id, code),
            )
            error = self._first_login_error(e.response.text)
            error_code = error.get("errorCode")
            if error_code in (
                "VALIDATION_CODE_INVALID",
                "VALIDATION_CODE_ALREADY_USED",
            ):
                return EntityLoginResult(LoginResultCode.INVALID_CODE)
            if e.response.status_code == 429 or error_code == "TOO_MANY_REQUESTS":
                return self._cooldown_result(error)
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Authenticator verification failed: {e.response.status_code}",
            )

        self._v2_authenticator_verified = True
        return EntityLoginResult(
            LoginResultCode.CODE_REQUESTED,
            confirmation_type=LoginConfirmationType.IN_APP,
            process_id=process_id,
        )

    async def _poll_weblogin_v2(self, process_id: str) -> EntityLoginResult | None:
        api = self._tr_api
        if not api or api._process_id != process_id:
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="Login process is no longer active",
            )
        while True:
            if self._tr_api is not api:
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Login process is no longer active",
                )
            if self._cancel_event.is_set():
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Login cancelled by user.",
                )
            try:
                r = await api._websession.get(
                    f"{api._host}/api/v2/auth/web/login/processes/{process_id}",
                    headers=await self._get_v2_headers(),
                )
                if self._tr_api is not api:
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR,
                        message="Login process is no longer active",
                    )
                if self._cancel_event.is_set():
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR,
                        message="Login cancelled by user.",
                    )
                r.raise_for_status()
                j = await r.json()

                if not isinstance(j, dict):
                    self._log.error("Trade Republic login returned an invalid process")
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR,
                        message="Invalid login process response",
                    )
                raw_status = j.get("status")
                status = raw_status.upper() if isinstance(raw_status, str) else ""
                if status in ("CONFIRMED", "COMPLETED"):
                    self._log.info("TR in-app confirmation succeeded")
                    return None

                raw_expires = j.get("expiresAt")
                if raw_expires is not None and raw_expires != "":
                    try:
                        if isinstance(raw_expires, int) and not isinstance(
                            raw_expires, bool
                        ):
                            seconds = (
                                raw_expires // 1000
                                if raw_expires > 100000000000
                                else raw_expires
                            )
                            self._v2_deadline = datetime.fromtimestamp(
                                seconds, tzlocal()
                            )
                        else:
                            self._v2_deadline = datetime.fromisoformat(raw_expires)
                            if self._v2_deadline.tzinfo is None:
                                self._v2_deadline = self._v2_deadline.replace(
                                    tzinfo=tzlocal()
                                )
                    except (TypeError, ValueError, OverflowError, OSError):
                        self._log.warning(
                            "Trade Republic login returned an invalid expiry"
                        )
                if self._v2_deadline is None:
                    self._v2_deadline = datetime.now(tzlocal()) + timedelta(
                        seconds=self.IN_APP_TIMEOUT_SECONDS
                    )

                if datetime.now(tzlocal()) >= self._v2_deadline:
                    break

                if status and status != "PENDING":
                    self._log.error("Trade Republic login returned an unknown status")
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR,
                        message="Unexpected login process status",
                    )

                if (
                    j.get("requiredAction") == "AUTHENTICATOR_VERIFICATION"
                    and not self._v2_authenticator_verified
                ):
                    self._v2_authenticator_required = True
                    return EntityLoginResult(
                        LoginResultCode.CODE_REQUESTED,
                        confirmation_type=LoginConfirmationType.AUTHENTICATOR,
                        process_id=process_id,
                        details={"pinLength": self.AUTHENTICATOR_CODE_LENGTH},
                    )

                if not status:
                    self._log.error("Trade Republic login returned an unknown status")
                    return EntityLoginResult(
                        LoginResultCode.UNEXPECTED_ERROR,
                        message="Unexpected login process status",
                    )

                self._log.debug("TR in-app confirmation pending")
            except httpx.HTTPStatusError as e:
                self._log_login_error(
                    "v2 login process",
                    e.response.status_code,
                    e.response.text,
                    (process_id,),
                )
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Error checking login status: {e.response.status_code}",
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._log.error("Trade Republic login returned invalid process JSON")
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Invalid login process response",
                )

            await asyncio.sleep(self.IN_APP_POLL_INTERVAL)
            if self._cancel_event.is_set():
                self._log.info("TR in-app confirmation cancelled by user")
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Login cancelled by user.",
                )

        self._log.warning("TR in-app confirmation timed out")
        return EntityLoginResult(
            LoginResultCode.UNEXPECTED_ERROR,
            message="In-app confirmation timed out. Please try again.",
        )

    def _export_session(self, waf_token: str) -> dict:
        return {
            "cookies": _json_cookie_jar(self._tr_api._websession.cookies),
            "waf_token": waf_token,
            "stable_device_id": self._stable_device_id,
        }

    def _inject_session(self, session: EntitySession):
        cookies = _rebuild_cookie_jar(session.payload["cookies"])
        self._tr_api._websession.clear_cookies()
        for cookie in cookies.jar:
            self._tr_api._websession.set_cookie(cookie)
        waf_token = session.payload.get("waf_token")
        if waf_token:
            self._tr_api._websession.headers["x-aws-waf-token"] = waf_token
        stable_id = session.payload.get("stable_device_id")
        if stable_id:
            self._stable_device_id = stable_id
        self._tr_api._weblogin = True

    async def close(self):
        if not self._tr_api:
            return
        try:
            await self._tr_api.close()
        except Exception:
            self._log.debug("Error closing Trade Republic websocket", exc_info=True)

    @cached(ttl=120, noself=True)
    async def get_portfolio(self):
        portfolio = Portfolio(self._tr_api)
        await portfolio.portfolio_loop()
        return portfolio

    async def get_details(
        self,
        isin: str,
        types: Optional[list] = None,
    ):
        if types is None:
            types = ["stockDetails", "mutualFundDetails", "instrument"]
        details = TRDetails(self._tr_api, isin)
        await details.fetch(types)
        return details

    async def get_transactions(
        self,
        since: Optional[datetime] = None,
        already_registered_ids: set[str] = None,
        with_details: bool = True,
    ):
        requested_data = ["timelineTransactions"]
        if with_details:
            requested_data.append("timelineDetailV2")
        dl = TRTimeline(
            self._tr_api,
            since=since,
            requested_data=requested_data,
            already_registered_ids=already_registered_ids,
        )
        return await dl.fetch()

    async def get_user_info(self):
        return await self._tr_api.settings()

    async def get_interest_payouts(self, number_of_payouts: int):
        r = await self._tr_api._web_request(
            f"/api/v1/banking/consumer/interest/payouts?numberOfPayouts={number_of_payouts}"
        )
        r.raise_for_status()
        return await r.json()

    async def get_active_interest_rate(self, account_number: str):
        r = await self._tr_api._web_request(
            f"/api/v1/banking/consumer/interest/{account_number}/rate"
        )
        r.raise_for_status()
        return await r.json()

    async def get_interest_payout_summary(
        self, decimal_separator: str = ",", grouping_separator: str = "."
    ):
        r = await self._tr_api._web_request(
            f"/api/v1/interest/details-screen?decimalSeparator={decimal_separator}&groupingSeparator={grouping_separator}"
        )
        r.raise_for_status()
        return await r.json()

    async def get_portfolio_by_type(self, securities_account_num: Optional[str] = None):
        request = {"type": "compactPortfolioByType"}
        if securities_account_num:
            request["secAccNo"] = securities_account_num
        await self._tr_api.subscribe(request)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    async def get_saving_plans(
        self, securities_account_num: Optional[str] = None
    ) -> dict:
        request = {"type": "savingsPlans"}
        if securities_account_num:
            request["secAccNo"] = securities_account_num
        await self._tr_api.subscribe(request)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    async def get_private_markets_portfolio_status(self) -> dict:
        await self._tr_api.subscribe({"type": "privateMarketsPortfolioStatus"})
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    async def get_private_markets_orders(
        self, securities_account_num: Optional[str] = None
    ) -> dict:
        request = {"type": "privateMarketsOrders"}
        if securities_account_num:
            request["secAccNo"] = securities_account_num
        await self._tr_api.subscribe(request)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    async def get_private_markets_portfolio(self, securities_account_num: str) -> dict:
        request = {
            "type": "privateMarketsPositions",
            "secAccNo": securities_account_num,
        }
        await self._tr_api.subscribe(request)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    @cached(ttl=60, noself=True)
    async def get_instrument_details(self, isin: str) -> dict:
        await self._tr_api.instrument_details(isin)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    @cached(ttl=60, noself=True)
    async def get_stock_details(self, isin: str) -> dict:
        await self._tr_api.stock_details(isin)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    async def ticker(self, isin, exchange):
        await self._tr_api.ticker(isin, exchange=exchange)
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response

    @cached(ttl=43200, noself=True)
    async def get_fund_details(self, isin):
        await self._tr_api.subscribe({"type": "mutualFundDetails", "id": isin})
        subscription_id, _, response = await self._tr_api.recv()
        await self._tr_api.unsubscribe(subscription_id)
        return response
