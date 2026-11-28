import base64
import hashlib
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
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
)
from infrastructure.client.ai.chatgpt.chatgpt_oauth import (
    DEFAULT_COMPLETION_URL,
    DISCOVERY_URL,
    ISSUER,
    JWKS_URL,
    PENDING_AUTHORIZATION_TTL_SECONDS,
    RESOURCE,
    TOKEN_URL,
    ChatGPTOAuth,
)
from infrastructure.client.http.http_response import HttpResponse
from jwt.algorithms import RSAAlgorithm

HOST_ID = UUID("6f1c2d3e-4b5a-4c6d-8e7f-90a1b2c3d4e5")
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=tzlocal())
ISSUED = "oaiapp_issued"
KID = "signing-key"
SUBJECT = "user-subject"
EMAIL = "user@example.com"
PORT = 7592
DEEP_LINK = DEFAULT_COMPLETION_URL
LOOPBACK = "http://127.0.0.1:53123/auth/callback"
REVOCATION_URL = "https://auth.openai.com/oauth/revoke"
PLAN_SCOPES = (
    "chatgpt.tokens.use.direct email offline_access openid profile resource.invoke"
)
SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWKS = {
    "keys": [
        {
            **RSAAlgorithm.to_jwk(SIGNING_KEY.public_key(), as_dict=True),
            "kid": KID,
            "alg": "RS256",
            "use": "sig",
        }
    ]
}


class FakeHostIdentity:
    async def get_host_id(self) -> UUID:
        return HOST_ID


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakeSession:
    def __init__(self):
        self.token_responses: list = []
        self.token_forms: list[dict] = []
        self.revocations: list[dict] = []
        self.gets: list[str] = []
        self.revocation_error: Exception | None = None

    async def post(self, url, **kwargs):
        if url == TOKEN_URL:
            self.token_forms.append(kwargs["data"])
            response = self.token_responses.pop(0)
            if isinstance(response, Exception):
                raise response
            status, body = response
            return HttpResponse(httpx.Response(status, json=body))
        assert url == REVOCATION_URL
        if self.revocation_error:
            raise self.revocation_error
        self.revocations.append(kwargs["data"])
        return HttpResponse(httpx.Response(200))

    async def get(self, url, **kwargs):
        self.gets.append(url)
        if url == JWKS_URL:
            return HttpResponse(httpx.Response(200, json=JWKS))
        assert url == DISCOVERY_URL
        return HttpResponse(
            httpx.Response(200, json={"revocation_endpoint": REVOCATION_URL})
        )


def _oauth(
    session=None, callback_port=PORT, clock=None, send_host_id=False
) -> ChatGPTOAuth:
    return ChatGPTOAuth(
        FakeHostIdentity(),
        callback_port,
        session=session or FakeSession(),
        clock=clock or Clock(),
        now=lambda: NOW,
        send_host_id=send_host_id,
    )


def _params(link: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(link).query).items()}


def _id_token(
    nonce: str,
    audience: str = ISSUED,
    issuer: str = ISSUER,
    key=SIGNING_KEY,
    kid: str = KID,
    subject: str = SUBJECT,
) -> str:
    issued_at = int(time.time())
    return jwt.encode(
        {
            "iss": issuer,
            "aud": [audience],
            "sub": subject,
            "email": EMAIL,
            "nonce": nonce,
            "iat": issued_at,
            "exp": issued_at + 3600,
        },
        key,
        algorithm="RS256",
        headers={"kid": kid},
    )


def _token_body(nonce: str, **overrides) -> dict:
    return {
        "access_token": "access-1",
        "refresh_token": "refresh-1",
        "id_token": _id_token(nonce),
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": PLAN_SCOPES,
        "earliest_refresh_at": int((NOW + timedelta(minutes=30)).timestamp()),
        **overrides,
    }


def _complete_request(state: str, **kwargs):
    return CompleteExternalIntegrationConnectionRequest(
        ExternalIntegrationId.CHATGPT,
        state,
        **{"code": "auth-code", "client_id": ISSUED, **kwargs},
    )


async def _start(oauth: ChatGPTOAuth, completion_url=DEEP_LINK, previous=None):
    link = await oauth.start(completion_url, previous)
    params = _params(link)
    return link, params, oauth._pending[params["state"]]


class TestStartAuthorization:
    @pytest.mark.asyncio
    async def test_registers_a_new_client_through_the_backend_callback(self):
        oauth = _oauth()

        link, params, pending = await _start(oauth)

        assert link.startswith("https://auth.openai.com/api/accounts/authorize?")
        assert "scope=openid%20profile%20email" in link
        assert params["client_id"] == "dynamic_agent_client"
        assert params["agent_name_hint"] == "Finanze"
        assert "ext_agent_host_id" not in params
        assert params["redirect_uri"] == f"http://127.0.0.1:{PORT}/auth/callback"
        assert params["response_type"] == "code"
        assert params["resource"] == RESOURCE
        assert params["scope"].split() == [
            "openid",
            "profile",
            "email",
            "offline_access",
            "resource.invoke",
            "chatgpt.tokens.use.direct",
        ]
        assert params["code_challenge_method"] == "S256"
        assert len(pending.verifier) == 43
        expected_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(pending.verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        assert params["code_challenge"] == expected_challenge
        assert params["nonce"] == pending.nonce
        assert "id_token_hint" not in params
        assert oauth.destination(params["state"]) == DEEP_LINK

    @pytest.mark.asyncio
    async def test_sends_the_host_id_when_enabled(self):
        _, params, _ = await _start(_oauth(send_host_id=True))

        assert params["ext_agent_host_id"] == f"urn:uuid:{HOST_ID}"

    @pytest.mark.asyncio
    async def test_loopback_completion_url_is_the_redirect_uri(self):
        oauth = _oauth(callback_port=None)

        _, params, _ = await _start(oauth, LOOPBACK)

        assert params["redirect_uri"] == LOOPBACK
        assert oauth.destination(params["state"]) is None

    @pytest.mark.asyncio
    async def test_requires_a_loopback_callback_without_backend_port(self):
        with pytest.raises(IntegrationSetupError) as error:
            await _oauth(callback_port=None).start(DEEP_LINK)

        assert error.value.code == IntegrationSetupErrorCode.UNKNOWN

    @pytest.mark.asyncio
    async def test_defaults_to_the_desktop_deep_link(self):
        oauth = _oauth()

        _, params, _ = await _start(oauth, None)

        assert oauth.destination(params["state"]) == DEFAULT_COMPLETION_URL

    @pytest.mark.asyncio
    async def test_reauthorization_reuses_the_issued_client_and_hints(self):
        previous = {
            "client_id": ISSUED,
            "id_token": "previous-id-token",
            "email": EMAIL,
            "subject": SUBJECT,
        }

        link, params, pending = await _start(_oauth(), previous=previous)

        assert params["client_id"] == ISSUED
        assert params["login_hint"] == EMAIL
        assert "previous-id-token" not in link
        assert "agent_name_hint" not in params
        assert pending.client_id == ISSUED

    @pytest.mark.asyncio
    async def test_destination_expires_with_the_pending_authorization(self):
        clock = Clock()
        oauth = _oauth(clock=clock)
        _, params, _ = await _start(oauth)

        clock.now += PENDING_AUTHORIZATION_TTL_SECONDS + 1

        assert oauth.destination(params["state"]) is None


class TestCompleteAuthorization:
    @pytest.mark.asyncio
    async def test_exchanges_the_code_and_returns_credentials(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, pending = await _start(oauth)
        body = _token_body(pending.nonce)
        session.token_responses.append((200, body))

        payload = await oauth.complete(_complete_request(params["state"]))

        assert session.token_forms == [
            {
                "grant_type": "authorization_code",
                "client_id": ISSUED,
                "code": "auth-code",
                "code_verifier": pending.verifier,
                "redirect_uri": f"http://127.0.0.1:{PORT}/auth/callback",
                "resource": RESOURCE,
            }
        ]
        assert payload == {
            "client_id": ISSUED,
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "id_token": body["id_token"],
            "scope": PLAN_SCOPES,
            "expires_at": (NOW + timedelta(hours=1)).isoformat(),
            "refresh_after": (NOW + timedelta(minutes=30)).isoformat(),
            "subject": SUBJECT,
            "email": EMAIL,
        }

    @pytest.mark.asyncio
    async def test_state_is_single_use(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, pending = await _start(oauth)
        session.token_responses.append((200, _token_body(pending.nonce)))
        await oauth.complete(_complete_request(params["state"]))

        with pytest.raises(IntegrationSetupError) as error:
            await oauth.complete(_complete_request(params["state"]))

        assert error.value.code == IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED

    @pytest.mark.asyncio
    async def test_expired_state_is_rejected(self):
        clock = Clock()
        session = FakeSession()
        oauth = _oauth(session, clock=clock)
        _, params, _ = await _start(oauth)
        clock.now += PENDING_AUTHORIZATION_TTL_SECONDS + 1

        with pytest.raises(IntegrationSetupError) as error:
            await oauth.complete(_complete_request(params["state"]))

        assert error.value.code == IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED
        assert session.token_forms == []

    @pytest.mark.asyncio
    async def test_denied_consent_is_not_exchanged(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, _ = await _start(oauth)

        with pytest.raises(IntegrationSetupError) as error:
            await oauth.complete(
                _complete_request(params["state"], code=None, error="access_denied")
            )

        assert error.value.code == IntegrationSetupErrorCode.AUTHORIZATION_DENIED
        assert session.token_forms == []

    @pytest.mark.asyncio
    async def test_new_registration_requires_the_issued_client_id(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, _ = await _start(oauth)

        with pytest.raises(IntegrationSetupError) as error:
            await oauth.complete(_complete_request(params["state"], client_id=None))

        assert error.value.code == IntegrationSetupErrorCode.UNKNOWN
        assert session.token_forms == []

    @pytest.mark.asyncio
    async def test_reauthorization_rejects_a_different_client(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, _ = await _start(oauth, previous={"client_id": ISSUED})

        with pytest.raises(IntegrationSetupError):
            await oauth.complete(
                _complete_request(params["state"], client_id="oaiapp_other")
            )

        assert session.token_forms == []

    @pytest.mark.asyncio
    async def test_reauthorization_keeps_the_pending_client_when_omitted(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, pending = await _start(
            oauth, previous={"client_id": ISSUED, "subject": SUBJECT}
        )
        session.token_responses.append((200, _token_body(pending.nonce)))

        payload = await oauth.complete(
            _complete_request(params["state"], client_id=None)
        )

        assert payload["client_id"] == ISSUED
        assert session.token_forms[0]["client_id"] == ISSUED

    @pytest.mark.asyncio
    async def test_reauthorization_with_another_account_is_denied(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, pending = await _start(
            oauth, previous={"client_id": ISSUED, "subject": SUBJECT}
        )
        session.token_responses.append(
            (
                200,
                _token_body(
                    pending.nonce,
                    id_token=_id_token(pending.nonce, subject="someone-else"),
                ),
            )
        )

        with pytest.raises(IntegrationSetupError) as error:
            await oauth.complete(_complete_request(params["state"]))

        assert error.value.code == IntegrationSetupErrorCode.AUTHORIZATION_DENIED

    @pytest.mark.asyncio
    async def test_missing_plan_permission_is_denied(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, pending = await _start(oauth)
        session.token_responses.append(
            (200, _token_body(pending.nonce, scope="openid profile email"))
        )

        with pytest.raises(IntegrationSetupError) as error:
            await oauth.complete(_complete_request(params["state"]))

        assert error.value.code == IntegrationSetupErrorCode.AUTHORIZATION_DENIED

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "token_factory",
        [
            lambda nonce: _id_token("other-nonce"),
            lambda nonce: _id_token(nonce, audience="oaiapp_other"),
            lambda nonce: _id_token(nonce, issuer="https://evil.example"),
            lambda nonce: _id_token(nonce, key=OTHER_KEY),
            lambda nonce: _id_token(nonce, key=OTHER_KEY, kid="unknown"),
            lambda nonce: None,
        ],
        ids=[
            "nonce",
            "audience",
            "issuer",
            "signature",
            "unknown-key",
            "missing",
        ],
    )
    async def test_invalid_id_token_is_rejected(self, token_factory):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, pending = await _start(oauth)
        session.token_responses.append(
            (200, _token_body(pending.nonce, id_token=token_factory(pending.nonce)))
        )

        with pytest.raises(IntegrationSetupError) as error:
            await oauth.complete(_complete_request(params["state"]))

        assert error.value.code == IntegrationSetupErrorCode.INVALID_CREDENTIALS

    @pytest.mark.asyncio
    async def test_rejected_registration_code_requires_another_authorization(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, _ = await _start(oauth)
        session.token_responses.append((400, {"error": "invalid_grant"}))

        with pytest.raises(IntegrationSetupError) as error:
            await oauth.complete(_complete_request(params["state"]))

        assert (
            error.value.code == IntegrationSetupErrorCode.AUTHORIZATION_RETRY_REQUIRED
        )

    @pytest.mark.asyncio
    async def test_rejected_code_of_issued_client_expires_the_authorization(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, _ = await _start(oauth, previous={"client_id": ISSUED})
        session.token_responses.append((400, {"error": "invalid_grant"}))

        with pytest.raises(IntegrationSetupError) as error:
            await oauth.complete(_complete_request(params["state"]))

        assert error.value.code == IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED

    @pytest.mark.asyncio
    async def test_retry_after_rejected_code_reuses_the_issued_client(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, first, _ = await _start(oauth)
        session.token_responses.append(
            (400, {"error": "invalid_grant", "error_description": "Invalid code"})
        )
        with pytest.raises(IntegrationSetupError):
            await oauth.complete(_complete_request(first["state"]))

        _, retry, pending = await _start(oauth)
        session.token_responses.append((200, _token_body(pending.nonce)))
        payload = await oauth.complete(
            _complete_request(retry["state"], client_id=None)
        )

        assert retry["client_id"] == ISSUED
        assert "agent_name_hint" not in retry
        assert payload["client_id"] == ISSUED
        assert session.token_forms[-1]["client_id"] == ISSUED

        _, next_sign_in, _ = await _start(oauth)
        assert next_sign_in["client_id"] == "dynamic_agent_client"

    @pytest.mark.asyncio
    async def test_network_failure_is_unreachable(self):
        session = FakeSession()
        oauth = _oauth(session)
        _, params, _ = await _start(oauth)
        session.token_responses.append(httpx.ConnectError("offline"))

        with pytest.raises(IntegrationSetupError) as error:
            await oauth.complete(_complete_request(params["state"]))

        assert error.value.code == IntegrationSetupErrorCode.UNREACHABLE


STORED = {
    "client_id": ISSUED,
    "access_token": "access-1",
    "refresh_token": "refresh-1",
    "id_token": "id-token-1",
    "subject": SUBJECT,
    "email": EMAIL,
    "expires_at": NOW.isoformat(),
}


class TestRefresh:
    @pytest.mark.asyncio
    async def test_rotates_tokens_and_keeps_the_identity(self):
        session = FakeSession()
        session.token_responses.append(
            (
                200,
                {
                    "access_token": "access-2",
                    "refresh_token": "refresh-2",
                    "expires_in": 3600,
                    "scope": PLAN_SCOPES,
                },
            )
        )

        payload = await _oauth(session).refresh(STORED)

        assert session.token_forms == [
            {
                "grant_type": "refresh_token",
                "client_id": ISSUED,
                "refresh_token": "refresh-1",
                "resource": RESOURCE,
            }
        ]
        assert payload == {
            "client_id": ISSUED,
            "access_token": "access-2",
            "refresh_token": "refresh-2",
            "id_token": "id-token-1",
            "subject": SUBJECT,
            "email": EMAIL,
            "scope": PLAN_SCOPES,
            "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error",
        [
            "invalid_grant",
            "invalid_refresh_token",
            "token_expired",
            "refresh_token_expired",
            "refresh_token_invalidated",
            "refresh_token_reused",
        ],
    )
    async def test_unusable_refresh_token_requires_sign_in(self, error):
        session = FakeSession()
        session.token_responses.append((400, {"error": error}))

        with pytest.raises(AIProviderError) as raised:
            await _oauth(session).refresh(STORED)

        assert raised.value.code == AIProviderErrorCode.REAUTHENTICATION_REQUIRED

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response",
        [
            (503, {"error": "temporarily_unavailable"}),
            (400, {"error": "invalid_client"}),
            httpx.ConnectError("offline"),
        ],
        ids=["server", "client-config", "network"],
    )
    async def test_other_failures_keep_the_session(self, response):
        session = FakeSession()
        session.token_responses.append(response)

        with pytest.raises(AIProviderError) as raised:
            await _oauth(session).refresh(STORED)

        assert raised.value.code == AIProviderErrorCode.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_missing_refresh_token_requires_sign_in(self):
        with pytest.raises(AIProviderError) as raised:
            await _oauth().refresh({"client_id": ISSUED, "access_token": "a"})

        assert raised.value.code == AIProviderErrorCode.REAUTHENTICATION_REQUIRED


class TestRevoke:
    @pytest.mark.asyncio
    async def test_revokes_the_refresh_token_at_the_discovered_endpoint(self):
        session = FakeSession()

        await _oauth(session).revoke(STORED)

        assert DISCOVERY_URL in session.gets
        assert session.revocations == [
            {
                "token": "refresh-1",
                "token_type_hint": "refresh_token",
                "client_id": ISSUED,
            }
        ]

    @pytest.mark.asyncio
    async def test_network_failures_are_ignored(self):
        session = FakeSession()
        session.revocation_error = httpx.ConnectError("offline")

        await _oauth(session).revoke(STORED)

        assert session.revocations == []

    @pytest.mark.asyncio
    async def test_nothing_to_revoke_without_a_refresh_token(self):
        session = FakeSession()

        await _oauth(session).revoke({"client_id": ISSUED})

        assert session.gets == []
