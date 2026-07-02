import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from dateutil.tz import tzlocal
from tzlocal import get_localzone_name

from domain.entity_login import EntityLoginResult, EntitySession, LoginResultCode
from domain.public_keychain import PublicKeychain
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.client.http.http_session import get_http_session

API_KEY_NAME = "B100_AKEY"
APP_VERSION = "1.20.000"
DEVICE_BRAND = "Apple"
DEVICE_MODEL = "iPhone Air"
DEVICE_OS_NAME = "IOS"
DEVICE_OS_VERSION = "26.5.1"

TOKEN_FALLBACK_LIFETIME = 15 * 60  # seconds


class B100Client:
    BASE_URL = "https://apis.b100.es"

    def __init__(self):
        self._base_headers = {
            "x-app-version": APP_VERSION,
            "x-device-brand": DEVICE_BRAND,
            "x-device-model": DEVICE_MODEL,
            "x-device-os-name": DEVICE_OS_NAME,
            "x-device-os-version": DEVICE_OS_VERSION,
            "x-language": "es",
            "Content-Type": "application/json; charset=UTF-8",
        }

        self._device_id: Optional[str] = None
        self._session_id: Optional[str] = None
        self._license_id: Optional[str] = None
        self._customer_id: Optional[str] = None
        self._shared_key: Optional[str] = None
        self._token: Optional[str] = None
        self._token_expiration: Optional[datetime] = None
        self._session_key: Optional[bytes] = None

        self._challenge_token: Optional[str] = None
        self._challenge_id: Optional[str] = None
        self._provisioning_data: Optional[str] = None

        self._log = logging.getLogger(__name__)
        self._session = get_http_session()

    async def login(
        self,
        user: str,
        pin: str,
        session: Optional[EntitySession],
        otp: Optional[str] = None,
        keychain: Optional[PublicKeychain] = None,
    ) -> EntityLoginResult:
        if keychain:
            entry = keychain.get(API_KEY_NAME)
            if entry:
                self._base_headers["x-api-key"] = entry.decode()

        self._restore_session(session)

        if (
            session
            and self._token
            and self._session_key
            and self._token_expiration
            and self._token_expiration > datetime.now(tzlocal())
        ):
            return EntityLoginResult(LoginResultCode.RESUMED)

        if not self._device_id:
            self._device_id = str(uuid4()).upper()

        provisioned = bool(self._shared_key and self._customer_id and self._license_id)

        if not provisioned:
            if not otp:
                return await self._start_provisioning(user, pin)

            error = await self._complete_provisioning(user, pin, otp)
            if error is not None:
                return error

        return await self._do_login(user, pin)

    def _restore_session(self, session: Optional[EntitySession]):
        if not session:
            return
        payload = session.payload or {}
        self._device_id = payload.get("device_id")
        self._license_id = payload.get("license_id")
        self._customer_id = payload.get("customer_id")
        self._shared_key = payload.get("shared_key")
        self._token = payload.get("token")
        session_key = payload.get("session_key")
        self._session_key = bytes.fromhex(session_key) if session_key else None
        expiration = payload.get("expiration")
        self._token_expiration = (
            datetime.fromisoformat(expiration) if expiration else None
        )

    async def _start_provisioning(self, user: str, pin: str) -> EntityLoginResult:
        self._session_id = secrets.token_hex(32)
        headers = self._unsigned_headers()
        headers["x-session-id"] = self._session_id

        response = await self._session.request(
            "POST",
            self.BASE_URL + "/api/v1/auth/provisioning",
            content=json.dumps({"user": user, "pin": pin}),
            headers=headers,
        )

        body = await self._safe_json(response)
        if (
            response.status == 403
            and (body or {}).get("detail") == "CHALLENGE_REQUIRED"
        ):
            resp_headers = {k.lower(): v for k, v in response.headers.items()}
            authorization = resp_headers.get("authorization", "")
            self._challenge_token = authorization.removeprefix("Bearer ").strip()
            self._challenge_id = resp_headers.get("x-challenge-id")
            self._provisioning_data = resp_headers.get("x-provisioning-data")

            if not (
                self._challenge_token and self._challenge_id and self._provisioning_data
            ):
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message="Missing challenge headers in provisioning response",
                )

            properties = (body or {}).get("properties") or {}
            return EntityLoginResult(
                LoginResultCode.CODE_REQUESTED,
                process_id=self._challenge_id,
                details={"hint": properties.get("solutionHint")},
            )

        if response.status in (400, 401, 403):
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

        self._log.error(f"Unexpected provisioning response {response.status}: {body}")
        return EntityLoginResult(
            LoginResultCode.UNEXPECTED_ERROR,
            message=f"Unexpected provisioning response {response.status}",
        )

    async def _complete_provisioning(
        self, user: str, pin: str, otp: str
    ) -> Optional[EntityLoginResult]:
        if not (
            self._challenge_token and self._challenge_id and self._provisioning_data
        ):
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="Missing challenge state to complete provisioning",
            )

        headers = self._unsigned_headers()
        headers["x-session-id"] = self._session_id
        headers["Authorization"] = f"Bearer {self._challenge_token}"
        headers["x-challenge-id"] = self._challenge_id
        headers["x-provisioning-data"] = self._provisioning_data
        headers["x-challenge-response"] = otp

        response = await self._session.request(
            "POST",
            self.BASE_URL + "/api/v1/auth/provisioning",
            content=json.dumps({"user": user, "pin": pin}),
            headers=headers,
        )

        body = await self._safe_json(response)
        if response.ok and body and "sharedKey" in body:
            self._license_id = body["licenseId"]
            self._customer_id = body["customerId"]
            self._shared_key = body["sharedKey"]
            self._challenge_token = None
            self._challenge_id = None
            self._provisioning_data = None
            return None

        if response.status in (400, 401, 403):
            return EntityLoginResult(LoginResultCode.INVALID_CODE)

        self._log.error(
            f"Unexpected provisioning completion response {response.status}: {body}"
        )
        return EntityLoginResult(
            LoginResultCode.UNEXPECTED_ERROR,
            message=f"Unexpected provisioning completion response {response.status}",
        )

    async def _do_login(self, user: str, pin: str) -> EntityLoginResult:
        if not self._session_id:
            self._session_id = secrets.token_hex(32)

        headers = self._unsigned_headers()
        headers["x-session-id"] = self._session_id
        headers["x-license-id"] = self._license_id

        response = await self._session.request(
            "POST",
            self.BASE_URL + "/api/v1/auth/login",
            content=json.dumps({"user": user, "pin": pin}),
            headers=headers,
        )

        if response.status in (401, 403):
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

        if not response.ok:
            body = await response.text()
            self._log.error(f"Unexpected login response {response.status}: {body}")
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message=f"Unexpected login response {response.status}",
            )

        body = await response.json()
        self._token = body["token"]
        self._token_expiration = self._parse_expiration(body.get("expiresAt"))

        challenge_data = body.get("challengeData") or {}
        self._session_key = self._derive_session_key(
            challenge_data.get("d1"),
            challenge_data.get("d2"),
            challenge_data.get("d3"),
        )

        new_session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=self._token_expiration,
            payload={
                "device_id": self._device_id,
                "license_id": self._license_id,
                "customer_id": self._customer_id,
                "shared_key": self._shared_key,
                "token": self._token,
                "expiration": self._token_expiration.isoformat(),
                "session_key": self._session_key.hex(),
            },
        )
        return EntityLoginResult(LoginResultCode.CREATED, session=new_session)

    def _derive_session_key(self, d1, d2, d3) -> bytes:
        salt = (
            f"{self._customer_id}{self._license_id}{self._device_id}{d1}{d2}{d3}"
        ).encode("utf-8")
        return hashlib.pbkdf2_hmac(
            "sha256", self._shared_key.encode("utf-8"), salt, 65536, 32
        )

    def _sign(self, method: str, url: str, body: Optional[str]) -> str:
        text = f"{method}//{url}"
        if body:
            text += f"//{body}"
        return hmac.new(
            self._session_key, text.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def _unsigned_headers(self) -> dict:
        headers = dict(self._base_headers)
        headers["x-device-id"] = self._device_id
        headers["x-device-datetime"] = self._device_datetime()
        return headers

    def _auth_headers(self) -> dict:
        headers = self._unsigned_headers()
        headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _signed_get(self, path: str, params: Optional[dict] = None) -> dict:
        url = self.BASE_URL + path
        if params:
            from urllib.parse import urlencode

            url = url + "?" + urlencode(params)

        headers = self._auth_headers()
        headers["x-signature"] = self._sign("GET", url, None)

        response = await self._session.request("GET", url, headers=headers)
        if not response.ok:
            body = await response.text()
            self._log.error(f"Error response for {path}: {response.status} {body}")
            response.raise_for_status()
        return await response.json()

    @staticmethod
    def _device_datetime() -> str:
        now = datetime.now(tzlocal())
        base = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}"
        offset = now.strftime("%z")
        offset = offset[:3] + ":" + offset[3:]
        try:
            zone = get_localzone_name()
        except Exception:
            zone = "UTC"
        return f"{base}{offset}[{zone}]"

    @staticmethod
    def _parse_expiration(value: Optional[str]) -> datetime:
        if value:
            try:
                normalized = value.replace("Z", "+00:00")
                match = re.match(r"^(.*\.\d{6})\d*([+-]\d{2}:\d{2})$", normalized)
                if match:
                    normalized = match.group(1) + match.group(2)
                return datetime.fromisoformat(normalized).astimezone(tzlocal())
            except Exception:
                pass
        return datetime.now(tzlocal()) + timedelta(seconds=TOKEN_FALLBACK_LIFETIME)

    async def _safe_json(self, response: HttpResponse) -> Optional[dict]:
        try:
            return await response.json()
        except Exception:
            return None

    async def get_accounts(self) -> list:
        return await self._signed_get("/api/v1/account")

    async def get_account(self, account_id: str) -> dict:
        return await self._signed_get(
            f"/api/v1/account/{account_id}", {"remunerationInfo": "true"}
        )

    async def get_cards(self) -> list:
        return await self._signed_get("/api/v1/card")

    async def get_card(self, card_id: str) -> dict:
        return await self._signed_get(f"/api/v1/card/{card_id}")

    async def get_account_movements(
        self, account_id: str, page_size: int = 50, cursor: Optional[str] = None
    ) -> dict:
        if cursor:
            decoded = json.loads(base64.b64decode(cursor))
            params = {k: v[0] if isinstance(v, list) else v for k, v in decoded.items()}
        else:
            params = {"pageSize": page_size}
        return await self._signed_get(f"/api/v1/account/{account_id}/movement", params)
