import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
from urllib.parse import quote, urlencode, urlsplit

import httpx
import jwt
from application.ports.host_identity_port import HostIdentityPort
from dateutil.tz import tzlocal
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    CompleteExternalIntegrationConnectionRequest,
    ExternalIntegrationId,
    ExternalIntegrationPayload,
)

from infrastructure.client.http.http_session import HttpSession, get_http_session

ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/api/accounts/authorize"
TOKEN_URL = f"{ISSUER}/api/accounts/oauth/token"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
RESOURCE = "https://api.openai.com/v1"
DYNAMIC_CLIENT_ID = "dynamic_agent_client"
AGENT_NAME = "Finanze"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = (
    "openid",
    "profile",
    "email",
    "offline_access",
    "resource.invoke",
    PLAN_SCOPE,
)
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PATH = "/auth/callback"
DEFAULT_COMPLETION_URL = (
    "finanze://integration/complete?integration_oauth="
    + ExternalIntegrationId.CHATGPT.value
)
PENDING_AUTHORIZATION_TTL_SECONDS = 15 * 60
REQUEST_TIMEOUT_SECONDS = 30
JWKS_TTL_SECONDS = 60 * 60
ID_TOKEN_LEEWAY_SECONDS = 60
REAUTHENTICATION_ERRORS = {
    "invalid_grant",
    "invalid_refresh_token",
    "token_expired",
    "refresh_token_expired",
    "refresh_token_invalidated",
    "refresh_token_reused",
}


class _TransientError(Exception):
    pass


class _OAuthError(Exception):
    def __init__(
        self,
        code: str,
        description: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        self.code = code
        self.description = description
        self.request_id = request_id
        super().__init__(code)

    def __str__(self) -> str:
        details = ", ".join(
            value for value in (self.description, self.request_id) if value
        )
        return f"{self.code} ({details})" if details else self.code


@dataclass(frozen=True)
class _PendingAuthorization:
    client_id: Optional[str]
    subject: Optional[str]
    verifier: str
    nonce: str
    redirect_uri: str
    destination: Optional[str]
    expires_at: float


def _local_now() -> datetime:
    return datetime.now(tzlocal())


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def loopback_callback_uri(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if (
        parts.scheme != "http"
        or parts.hostname != CALLBACK_HOST
        or not port
        or parts.path != CALLBACK_PATH
        or parts.query
        or parts.fragment
    ):
        return None
    return f"http://{CALLBACK_HOST}:{port}{CALLBACK_PATH}"


def _parse_instant(value: Any) -> Optional[datetime]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tzlocal())
        if isinstance(value, str) and value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return datetime.fromtimestamp(float(value), tzlocal())
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=tzlocal())
    except (ValueError, OverflowError, OSError):
        return None
    return None


class ChatGPTOAuth:
    def __init__(
        self,
        host_identity: HostIdentityPort,
        callback_port: Optional[int],
        session: Optional[HttpSession] = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = _local_now,
        send_host_id: bool = False,
    ):
        self._host_identity = host_identity
        self._callback_port = callback_port
        self._session = session or get_http_session()
        self._clock = clock
        self._now = now
        # OpenAI's devkit keeps ext_agent_host_id off until the authorization server supports it.
        self._send_host_id = send_host_id
        self._pending: dict[str, _PendingAuthorization] = {}
        # A code can fail after registration succeeds; retrying must reuse the issued client.
        self._retained_client_id: Optional[str] = None
        self._jwks: Optional[tuple[float, dict[str, Any]]] = None
        self._revocation_endpoint: Optional[str] = None
        self._log = logging.getLogger(__name__)

    async def start(
        self,
        completion_url: Optional[str],
        previous: Optional[ExternalIntegrationPayload] = None,
    ) -> str:
        redirect_uri = loopback_callback_uri(completion_url)
        destination = None
        if redirect_uri is None:
            if self._callback_port is None:
                raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)
            redirect_uri = (
                f"http://{CALLBACK_HOST}:{self._callback_port}{CALLBACK_PATH}"
            )
            destination = completion_url or DEFAULT_COMPLETION_URL

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(32)
        issued_client_id = (previous or {}).get("client_id") or self._retained_client_id

        params = {
            "response_type": "code",
            "client_id": issued_client_id or DYNAMIC_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": " ".join(SCOPES),
            "resource": RESOURCE,
            "state": state,
            "nonce": nonce,
            "code_challenge": _code_challenge(verifier),
            "code_challenge_method": "S256",
        }
        if self._send_host_id:
            host_id = await self._host_identity.get_host_id()
            params["ext_agent_host_id"] = f"urn:uuid:{host_id}"
        if not issued_client_id:
            params["agent_name_hint"] = AGENT_NAME
        elif (previous or {}).get("email"):
            params["login_hint"] = previous["email"]

        now = self._clock()
        self._pending = {
            key: pending
            for key, pending in self._pending.items()
            if pending.expires_at > now
        }
        self._pending[state] = _PendingAuthorization(
            client_id=issued_client_id,
            subject=(previous or {}).get("subject") if issued_client_id else None,
            verifier=verifier,
            nonce=nonce,
            redirect_uri=redirect_uri,
            destination=destination,
            expires_at=now + PENDING_AUTHORIZATION_TTL_SECONDS,
        )
        return f"{AUTHORIZE_URL}?{urlencode(params, quote_via=quote)}"

    def destination(self, state: str) -> Optional[str]:
        pending = self._pending.get(state)
        if pending is None or pending.expires_at <= self._clock():
            return None
        return pending.destination

    async def complete(
        self, request: CompleteExternalIntegrationConnectionRequest
    ) -> ExternalIntegrationPayload:
        pending = self._pending.pop(request.state, None)
        if pending is None or pending.expires_at <= self._clock():
            raise IntegrationSetupError(IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED)

        if request.error:
            self._log.warning(f"ChatGPT authorization failed: {request.error}")
            if request.error == "access_denied":
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.AUTHORIZATION_DENIED
                )
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)

        if (
            pending.client_id
            and request.client_id
            and request.client_id != pending.client_id
        ):
            self._log.warning("ChatGPT callback returned a different client")
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)
        client_id = pending.client_id or request.client_id
        if not request.code or not client_id or client_id == DYNAMIC_CLIENT_ID:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)
        self._retained_client_id = client_id

        try:
            body = await self._token_request(
                {
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "code": request.code,
                    "code_verifier": pending.verifier,
                    "redirect_uri": pending.redirect_uri,
                    "resource": RESOURCE,
                }
            )
        except _TransientError as e:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNREACHABLE) from e
        except _OAuthError as e:
            self._log.warning(f"ChatGPT code exchange failed: {e}")
            if e.code == "invalid_grant" and pending.client_id is None:
                # OpenAI explains plan or consent problems only when the issued client authorizes again.
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.AUTHORIZATION_RETRY_REQUIRED
                ) from e
            if e.code == "invalid_grant":
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED
                ) from e
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN) from e

        id_token = body.get("id_token")
        claims = await self._verify_id_token(id_token, client_id, pending.nonce)
        if pending.subject and claims.get("sub") != pending.subject:
            raise IntegrationSetupError(IntegrationSetupErrorCode.AUTHORIZATION_DENIED)

        scopes = str(body.get("scope") or "").split()
        if PLAN_SCOPE not in scopes:
            raise IntegrationSetupError(IntegrationSetupErrorCode.AUTHORIZATION_DENIED)
        if not body.get("access_token") or not body.get("refresh_token"):
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)

        payload = self._token_payload(client_id, body, {})
        payload["id_token"] = id_token
        payload["subject"] = str(claims["sub"])
        email = claims.get("email")
        if isinstance(email, str) and email:
            payload["email"] = email
        self._retained_client_id = None
        return payload

    async def refresh(
        self, payload: ExternalIntegrationPayload
    ) -> ExternalIntegrationPayload:
        client_id = payload.get("client_id")
        refresh_token = payload.get("refresh_token")
        if not client_id or not refresh_token:
            raise AIProviderError(
                AIProviderErrorCode.REAUTHENTICATION_REQUIRED,
                "ChatGPT sign-in expired, sign in again",
            )

        try:
            body = await self._token_request(
                {
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": refresh_token,
                    "resource": RESOURCE,
                }
            )
        except _TransientError as e:
            raise AIProviderError(
                AIProviderErrorCode.UNAVAILABLE,
                "Could not refresh the ChatGPT session",
            ) from e
        except _OAuthError as e:
            self._log.warning(f"ChatGPT token refresh failed: {e}")
            if e.code in REAUTHENTICATION_ERRORS:
                raise AIProviderError(
                    AIProviderErrorCode.REAUTHENTICATION_REQUIRED,
                    "ChatGPT sign-in expired, sign in again",
                ) from e
            raise AIProviderError(
                AIProviderErrorCode.UNAVAILABLE,
                "Could not refresh the ChatGPT session",
            ) from e

        if not body.get("access_token"):
            raise AIProviderError(
                AIProviderErrorCode.UNAVAILABLE,
                "Could not refresh the ChatGPT session",
            )
        return self._token_payload(client_id, body, payload)

    async def revoke(self, payload: ExternalIntegrationPayload):
        client_id = payload.get("client_id")
        refresh_token = payload.get("refresh_token")
        if not client_id or not refresh_token:
            return
        try:
            endpoint = await self._revocation_url()
            response = await self._session.post(
                endpoint,
                data={
                    "token": refresh_token,
                    "token_type_hint": "refresh_token",
                    "client_id": client_id,
                },
                headers={"Accept": "application/json"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except (httpx.HTTPError, _TransientError):
            self._log.warning("Could not reach OpenAI to revoke the ChatGPT session")
            return
        if not response.ok:
            self._log.warning(
                f"OpenAI did not confirm the ChatGPT session revocation: {response.status}"
            )

    def _token_payload(
        self,
        client_id: str,
        body: dict,
        previous: ExternalIntegrationPayload,
    ) -> ExternalIntegrationPayload:
        payload = {
            key: value
            for key, value in previous.items()
            if key in ("id_token", "subject", "email")
        }
        payload["client_id"] = client_id
        payload["access_token"] = str(body["access_token"])
        payload["refresh_token"] = str(
            body.get("refresh_token") or previous.get("refresh_token") or ""
        )
        if isinstance(body.get("id_token"), str) and body["id_token"]:
            payload["id_token"] = body["id_token"]
        scope = body.get("scope")
        if isinstance(scope, str) and scope:
            payload["scope"] = scope
        expires_in = body.get("expires_in")
        if isinstance(expires_in, (int, float)) and not isinstance(expires_in, bool):
            payload["expires_at"] = (
                self._now() + timedelta(seconds=expires_in)
            ).isoformat()
        refresh_after = _parse_instant(body.get("earliest_refresh_at"))
        if refresh_after is not None:
            payload["refresh_after"] = refresh_after.isoformat()
        return payload

    async def _token_request(self, form: dict[str, str]) -> dict:
        try:
            response = await self._session.post(
                TOKEN_URL,
                data=form,
                headers={"Accept": "application/json"},
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
        if not response.ok:
            error = body.get("error")
            description = body.get("error_description") or body.get("error_reason")
            if isinstance(error, dict):
                description = error.get("message")
                error = error.get("code") or error.get("type")
            headers = {key.lower(): value for key, value in response.headers.items()}
            raise _OAuthError(
                str(error or response.status),
                description if isinstance(description, str) else None,
                headers.get("x-request-id") or headers.get("openai-request-id"),
            )
        return body

    async def _verify_id_token(self, id_token: Any, client_id: str, nonce: str) -> dict:
        if not isinstance(id_token, str) or not id_token:
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)
        try:
            header = jwt.get_unverified_header(id_token)
            key = await self._signing_key(header.get("kid"))
            claims = jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                audience=client_id,
                issuer=ISSUER,
                leeway=ID_TOKEN_LEEWAY_SECONDS,
                options={"require": ["sub", "exp", "iat"]},
            )
        except jwt.PyJWTError as e:
            self._log.warning(f"Invalid ChatGPT ID token: {type(e).__name__}")
            raise IntegrationSetupError(
                IntegrationSetupErrorCode.INVALID_CREDENTIALS
            ) from e
        if claims.get("nonce") != nonce or not claims.get("sub"):
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)
        return claims

    async def _signing_key(self, kid: Optional[str]) -> Any:
        keys = await self._signing_keys(force=False)
        if kid not in keys:
            keys = await self._signing_keys(force=True)
        if kid not in keys:
            raise jwt.InvalidKeyError("Unknown ChatGPT signing key")
        return keys[kid]

    async def _signing_keys(self, force: bool) -> dict[str, Any]:
        if (
            not force
            and self._jwks is not None
            and self._clock() - self._jwks[0] < JWKS_TTL_SECONDS
        ):
            return self._jwks[1]
        try:
            response = await self._session.get(
                JWKS_URL, timeout=REQUEST_TIMEOUT_SECONDS
            )
            if not response.ok:
                raise _TransientError()
            key_set = jwt.PyJWKSet.from_dict(await response.json())
        except (httpx.HTTPError, ValueError, _TransientError, jwt.PyJWKSetError) as e:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNREACHABLE) from e
        keys = {key.key_id: key.key for key in key_set.keys if key.key_id}
        self._jwks = (self._clock(), keys)
        return keys

    async def _revocation_url(self) -> str:
        if self._revocation_endpoint:
            return self._revocation_endpoint
        response = await self._session.get(
            DISCOVERY_URL, timeout=REQUEST_TIMEOUT_SECONDS
        )
        if not response.ok:
            raise _TransientError()
        try:
            endpoint = (await response.json()).get("revocation_endpoint")
        except (ValueError, AttributeError) as e:
            raise _TransientError() from e
        if not isinstance(endpoint, str) or urlsplit(endpoint).scheme != "https":
            raise _TransientError()
        self._revocation_endpoint = endpoint
        return endpoint
