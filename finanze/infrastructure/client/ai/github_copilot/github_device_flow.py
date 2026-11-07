import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

import httpx
from dateutil.tz import tzlocal
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    DeviceAuthorizationPollResult,
    DeviceAuthorizationStatus,
    ExternalIntegrationDeviceAuthorization,
    ExternalIntegrationPayload,
)

from infrastructure.client.http.http_session import HttpSession, get_http_session

DEVICE_CODE_URL = "https://github.com/login/device/code"
ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
VERIFICATION_URI = "https://github.com/login/device"
DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
REFRESH_GRANT_TYPE = "refresh_token"
DEFAULT_INTERVAL_SECONDS = 5
SLOW_DOWN_INCREMENT_SECONDS = 5
REQUEST_TIMEOUT_SECONDS = 30
TOKEN_EXPIRIES = (
    ("expires_in", "expires_at"),
    ("refresh_token_expires_in", "refresh_token_expires_at"),
)


@dataclass(eq=False)
class _PendingFlow:
    device_code: str
    interval: int
    expires_at: float
    next_poll_at: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def _local_now() -> datetime:
    return datetime.now(tzlocal())


class GitHubDeviceFlow:
    def __init__(
        self,
        client_id: str,
        scope: str,
        session: Optional[HttpSession] = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = _local_now,
    ):
        self._client_id = client_id
        self._scope = scope
        self._session = session or get_http_session()
        self._clock = clock
        self._now = now
        self._flows: dict[str, _PendingFlow] = {}
        self._log = logging.getLogger(__name__)

    async def start(self) -> ExternalIntegrationDeviceAuthorization:
        try:
            body = await self._post(
                DEVICE_CODE_URL, {"client_id": self._client_id, "scope": self._scope}
            )
        except _TransientError as e:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNREACHABLE) from e

        device_code = body.get("device_code")
        user_code = body.get("user_code")
        verification_uri = body.get("verification_uri")
        expires_in = body.get("expires_in")
        interval = body.get("interval", DEFAULT_INTERVAL_SECONDS)
        if (
            not isinstance(device_code, str)
            or not device_code
            or not isinstance(user_code, str)
            or not user_code
            or not isinstance(expires_in, int)
            or expires_in <= 0
            or not isinstance(interval, int)
            or interval < 0
        ):
            self._log.warning(
                f"Unexpected GitHub device code response: {body.get('error')}"
            )
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)
        if verification_uri != VERIFICATION_URI:
            self._log.warning("Rejected unexpected GitHub verification URI")
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)

        now = self._clock()
        interval = max(interval, 1)
        flow_id = secrets.token_urlsafe(24)
        self._flows = {
            flow_id: _PendingFlow(
                device_code=device_code,
                interval=interval,
                expires_at=now + expires_in,
                next_poll_at=now + interval,
            )
        }
        return ExternalIntegrationDeviceAuthorization(
            flow_id=flow_id,
            user_code=user_code,
            verification_uri=VERIFICATION_URI,
            expires_at=datetime.now(tzlocal()) + timedelta(seconds=expires_in),
            interval=interval,
        )

    async def poll(self, flow_id: str) -> DeviceAuthorizationPollResult:
        flow = self._flows.get(flow_id)
        if flow is None:
            raise IntegrationSetupError(IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED)
        if self._clock() >= flow.expires_at:
            self._flows.pop(flow_id, None)
            raise IntegrationSetupError(IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED)
        if flow.lock.locked() or self._clock() < flow.next_poll_at:
            return _pending(flow)

        async with flow.lock:
            try:
                body = await self._post(
                    ACCESS_TOKEN_URL,
                    {
                        "client_id": self._client_id,
                        "device_code": flow.device_code,
                        "grant_type": DEVICE_GRANT_TYPE,
                    },
                )
            except _TransientError:
                self._log.warning("Transient error polling GitHub device authorization")
                flow.next_poll_at = self._clock() + flow.interval
                return _pending(flow)

            access_token = body.get("access_token")
            if isinstance(access_token, str) and access_token:
                self._flows.pop(flow_id, None)
                return DeviceAuthorizationPollResult(
                    status=DeviceAuthorizationStatus.AUTHORIZED,
                    interval=flow.interval,
                    payload=self._token_payload(access_token, body),
                )

            error = body.get("error")
            if error == "authorization_pending":
                flow.next_poll_at = self._clock() + flow.interval
                return _pending(flow)
            if error == "slow_down":
                requested = body.get("interval")
                flow.interval = max(
                    flow.interval + SLOW_DOWN_INCREMENT_SECONDS,
                    requested if isinstance(requested, int) else 0,
                )
                flow.next_poll_at = self._clock() + flow.interval
                return _pending(flow)

            self._flows.pop(flow_id, None)
            if error == "access_denied":
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.AUTHORIZATION_DENIED
                )
            if error == "expired_token":
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED
                )
            self._log.warning(f"GitHub device authorization failed: {error}")
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)

    async def refresh(self, refresh_token: str) -> ExternalIntegrationPayload:
        try:
            body = await self._post(
                ACCESS_TOKEN_URL,
                {
                    "client_id": self._client_id,
                    "grant_type": REFRESH_GRANT_TYPE,
                    "refresh_token": refresh_token,
                },
            )
        except (_TransientError, IntegrationSetupError) as e:
            raise AIProviderError(
                AIProviderErrorCode.UNAVAILABLE,
                "Could not refresh the GitHub Copilot session",
            ) from e

        access_token = body.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            self._log.warning(f"GitHub token refresh failed: {body.get('error')}")
            raise AIProviderError(
                AIProviderErrorCode.INVALID_CREDENTIALS,
                "GitHub Copilot session expired, reconnect the integration",
            )
        return self._token_payload(access_token, body)

    def _token_payload(
        self, access_token: str, body: dict
    ) -> ExternalIntegrationPayload:
        payload = {"access_token": access_token}
        for key in ("token_type", "scope", "refresh_token"):
            value = body.get(key)
            if isinstance(value, str) and value:
                payload[key] = value
        now = self._now()
        for source, target in TOKEN_EXPIRIES:
            seconds = body.get(source)
            if isinstance(seconds, int) and seconds > 0:
                payload[target] = (now + timedelta(seconds=seconds)).isoformat()
        return payload

    async def _post(self, url: str, form: dict[str, str]) -> dict:
        try:
            response = await self._session.post(
                url,
                data=form,
                headers={"Accept": "application/json"},
                follow_redirects=False,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as e:
            raise _TransientError() from e

        if response.status >= 500 or response.status == 429:
            raise _TransientError()
        try:
            body = await response.json()
        except ValueError as e:
            raise _TransientError() from e
        if not isinstance(body, dict):
            raise _TransientError()
        if not response.ok and "error" not in body:
            self._log.warning(f"GitHub device flow request failed: {response.status}")
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)
        return body


class _TransientError(Exception):
    pass


def _pending(flow: _PendingFlow) -> DeviceAuthorizationPollResult:
    return DeviceAuthorizationPollResult(
        status=DeviceAuthorizationStatus.PENDING, interval=flow.interval
    )
