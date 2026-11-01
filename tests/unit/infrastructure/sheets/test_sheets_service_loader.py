import base64
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from domain.exception.exceptions import (
    ExternalIntegrationRequired,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    CompleteExternalIntegrationConnectionRequest,
    ExternalIntegrationId,
)
from google_auth_oauthlib.flow import Flow
from infrastructure.sheets import sheets_service_loader
from infrastructure.sheets.sheets_service_loader import (
    DEFAULT_COMPLETION_URL,
    RELAY_REDIRECT_URI,
    SCOPES,
    TOKEN_FILENAME,
    SheetsServiceLoader,
)
from oauthlib.oauth2.rfc6749.errors import InvalidClientError, InvalidGrantError

PAYLOAD = {"client_id": "client-id", "client_secret": "client-secret"}
COMPLETION_URL = "http://localhost:8080/?integration_oauth=GOOGLE_SHEETS#/entities"
TOKEN = {"access_token": "access", "refresh_token": "refresh", "scope": SCOPES}


def _query(link: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(link).query).items()}


def _decode_completion_url(state: str) -> str:
    encoded = state.split("~", 1)[1]
    return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()


def _request(state: str, code: str | None = "code", error: str | None = None):
    return CompleteExternalIntegrationConnectionRequest(
        ExternalIntegrationId.GOOGLE_SHEETS, state, code, error
    )


def _write_legacy_token(path, refresh_token="legacy-refresh"):
    (path / TOKEN_FILENAME).write_text(
        json.dumps(
            {
                "token": "legacy-access",
                "refresh_token": refresh_token,
                "client_id": "legacy-client",
                "client_secret": "legacy-secret",
                "scopes": SCOPES,
            }
        )
    )


@pytest.fixture
def loader(tmp_path):
    loader = SheetsServiceLoader()
    loader.connect(SimpleNamespace(path=tmp_path))
    return loader


async def _start(loader, completion_url=COMPLETION_URL) -> str:
    link = await loader.start_authorization(PAYLOAD, completion_url)
    return _query(link)["state"]


async def _expect_error(call, code: IntegrationSetupErrorCode):
    with pytest.raises(IntegrationSetupError) as error:
        await call
    assert error.value.code == code


class TestStartAuthorization:
    @pytest.mark.asyncio
    async def test_link_targets_relay_with_offline_consent_and_pkce(self, loader):
        link = await loader.start_authorization(PAYLOAD, COMPLETION_URL)
        query = _query(link)

        assert link.startswith("https://accounts.google.com/o/oauth2/auth?")
        assert query["client_id"] == "client-id"
        assert query["redirect_uri"] == RELAY_REDIRECT_URI
        assert query["response_type"] == "code"
        assert query["scope"] == SCOPES[0]
        assert query["access_type"] == "offline"
        assert query["prompt"] == "consent"
        assert query["code_challenge_method"] == "S256"
        assert query["code_challenge"]
        assert "client_secret" not in query
        assert _decode_completion_url(query["state"]) == COMPLETION_URL

    @pytest.mark.asyncio
    async def test_states_are_unique(self, loader):
        assert await _start(loader) != await _start(loader)

    @pytest.mark.asyncio
    async def test_defaults_to_desktop_completion_url(self, loader):
        state = await _start(loader, completion_url=None)
        assert _decode_completion_url(state) == DEFAULT_COMPLETION_URL

    @pytest.mark.asyncio
    async def test_requires_client_credentials(self, loader):
        await _expect_error(
            loader.start_authorization({"client_id": "client-id"}, None),
            IntegrationSetupErrorCode.INVALID_CREDENTIALS,
        )


class TestCompleteAuthorization:
    @pytest.mark.asyncio
    async def test_exchanges_code_for_refresh_token(self, loader):
        state = await _start(loader)
        with patch.object(
            Flow, "fetch_token", autospec=True, return_value=TOKEN
        ) as fetch_token:
            payload = await loader.complete_authorization(_request(state, "auth-code"))

        assert payload == {**PAYLOAD, "refresh_token": "refresh"}
        assert fetch_token.call_args.kwargs == {"code": "auth-code"}

    @pytest.mark.asyncio
    async def test_state_can_only_be_used_once(self, loader):
        state = await _start(loader)
        with patch.object(Flow, "fetch_token", return_value=TOKEN):
            await loader.complete_authorization(_request(state))
            await _expect_error(
                loader.complete_authorization(_request(state)),
                IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED,
            )

    @pytest.mark.asyncio
    async def test_unknown_state_is_expired(self, loader):
        await _start(loader)
        await _expect_error(
            loader.complete_authorization(_request("unknown")),
            IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED,
        )

    @pytest.mark.asyncio
    async def test_stale_state_is_expired(self, loader):
        state = await _start(loader)
        flow, _ = loader._pending[state]
        loader._pending[state] = (flow, 0)
        await _expect_error(
            loader.complete_authorization(_request(state)),
            IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED,
        )

    @pytest.mark.asyncio
    async def test_access_denied(self, loader):
        state = await _start(loader)
        await _expect_error(
            loader.complete_authorization(_request(state, None, "access_denied")),
            IntegrationSetupErrorCode.AUTHORIZATION_DENIED,
        )

    @pytest.mark.asyncio
    async def test_other_provider_errors_are_unknown(self, loader):
        state = await _start(loader)
        await _expect_error(
            loader.complete_authorization(_request(state, None, "server_error")),
            IntegrationSetupErrorCode.UNKNOWN,
        )

    @pytest.mark.asyncio
    async def test_missing_code_is_unknown(self, loader):
        state = await _start(loader)
        await _expect_error(
            loader.complete_authorization(_request(state, None)),
            IntegrationSetupErrorCode.UNKNOWN,
        )

    @pytest.mark.parametrize(
        "error, code",
        [
            (InvalidClientError(), IntegrationSetupErrorCode.INVALID_CREDENTIALS),
            (InvalidGrantError(), IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED),
            (
                Warning("Scope has changed"),
                IntegrationSetupErrorCode.AUTHORIZATION_DENIED,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_token_exchange_errors(self, loader, error, code):
        state = await _start(loader)
        with patch.object(Flow, "fetch_token", side_effect=error):
            await _expect_error(loader.complete_authorization(_request(state)), code)

    @pytest.mark.asyncio
    async def test_missing_spreadsheets_scope_is_denied(self, loader):
        state = await _start(loader)
        token = {**TOKEN, "scope": ["openid"]}
        with patch.object(Flow, "fetch_token", return_value=token):
            await _expect_error(
                loader.complete_authorization(_request(state)),
                IntegrationSetupErrorCode.AUTHORIZATION_DENIED,
            )

    @pytest.mark.asyncio
    async def test_missing_refresh_token_is_unknown(self, loader):
        state = await _start(loader)
        token = {"access_token": "access", "scope": SCOPES}
        with patch.object(Flow, "fetch_token", return_value=token):
            await _expect_error(
                loader.complete_authorization(_request(state)),
                IntegrationSetupErrorCode.UNKNOWN,
            )


class TestService:
    def test_uses_payload_refresh_token_and_caches(self, loader):
        payload = {**PAYLOAD, "refresh_token": "refresh"}
        with patch.object(sheets_service_loader, "build", MagicMock()) as build:
            first = loader.service(payload)
            second = loader.service(payload)
            loader.service({**payload, "refresh_token": "other"})

        assert first is second
        assert build.call_count == 2
        credentials = build.call_args_list[0].kwargs["credentials"]
        assert credentials.refresh_token == "refresh"
        assert credentials.client_id == "client-id"
        assert credentials.client_secret == "client-secret"

    def test_falls_back_to_legacy_token_file(self, loader, tmp_path):
        _write_legacy_token(tmp_path)
        with patch.object(sheets_service_loader, "build", MagicMock()) as build:
            loader.service(PAYLOAD)

        credentials = build.call_args.kwargs["credentials"]
        assert credentials.refresh_token == "legacy-refresh"

    def test_payload_refresh_token_takes_precedence_over_legacy(self, loader, tmp_path):
        _write_legacy_token(tmp_path)
        with patch.object(sheets_service_loader, "build", MagicMock()) as build:
            loader.service({**PAYLOAD, "refresh_token": "refresh"})

        assert build.call_args.kwargs["credentials"].refresh_token == "refresh"

    def test_requires_integration_without_credentials(self, loader):
        with pytest.raises(ExternalIntegrationRequired):
            loader.service(PAYLOAD)

    def test_requires_integration_with_invalid_legacy_file(self, loader, tmp_path):
        (tmp_path / TOKEN_FILENAME).write_text(json.dumps({"token": "x"}))
        with pytest.raises(ExternalIntegrationRequired):
            loader.service(PAYLOAD)


class TestTeardown:
    @pytest.mark.asyncio
    async def test_removes_legacy_token_and_pending_authorizations(
        self, loader, tmp_path
    ):
        _write_legacy_token(tmp_path)
        state = await _start(loader)

        await loader.teardown()

        assert not (tmp_path / TOKEN_FILENAME).exists()
        await _expect_error(
            loader.complete_authorization(_request(state)),
            IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED,
        )

    @pytest.mark.asyncio
    async def test_without_legacy_token(self, loader, tmp_path):
        await loader.teardown()
        assert not (tmp_path / TOKEN_FILENAME).exists()
