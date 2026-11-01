from unittest.mock import AsyncMock

import pytest
from application.ports.connectable_integration import ConnectableIntegration
from application.ports.oauth_connectable_integration import (
    OAuthConnectableIntegration,
)
from application.use_cases.complete_external_integration_connection import (
    CompleteExternalIntegrationConnectionImpl,
)
from application.use_cases.connect_external_integration import (
    ConnectExternalIntegrationImpl,
)
from domain.exception.exceptions import (
    IntegrationNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    CompleteExternalIntegrationConnectionRequest,
    ConnectedExternalIntegrationRequest,
    ExternalIntegrationId,
)

SHEETS = ExternalIntegrationId.GOOGLE_SHEETS
PAYLOAD = {"client_id": "client-id", "client_secret": "client-secret"}
COMPLETED_PAYLOAD = {**PAYLOAD, "refresh_token": "refresh"}
LINK = "https://accounts.example/authorize"
COMPLETION_URL = "http://localhost:8080/?integration_oauth=GOOGLE_SHEETS"


class FakeOAuthIntegration(OAuthConnectableIntegration):
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.started = []
        self.completed = []

    async def start_authorization(self, payload, completion_url):
        self.started.append((payload, completion_url))
        if self.error:
            raise self.error
        return LINK

    async def complete_authorization(self, request):
        self.completed.append(request)
        if self.error:
            raise self.error
        return COMPLETED_PAYLOAD


class FakeIntegration(ConnectableIntegration):
    def __init__(self):
        self.payloads = []

    async def setup(self, payload):
        self.payloads.append(payload)


def _complete_request(**kwargs):
    return CompleteExternalIntegrationConnectionRequest(
        SHEETS, kwargs.pop("state", "state"), **kwargs
    )


class TestConnectOAuthIntegration:
    @pytest.mark.asyncio
    async def test_returns_link_without_activating(self):
        port = AsyncMock()
        integration = FakeOAuthIntegration()
        result = await ConnectExternalIntegrationImpl(
            port, {SHEETS: integration}
        ).execute(ConnectedExternalIntegrationRequest(SHEETS, PAYLOAD, COMPLETION_URL))

        assert result.link == LINK
        assert integration.started == [(PAYLOAD, COMPLETION_URL)]
        port.activate.assert_not_called()

    @pytest.mark.asyncio
    async def test_setup_errors_are_propagated(self):
        port = AsyncMock()
        integration = FakeOAuthIntegration(
            IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)
        )
        with pytest.raises(IntegrationSetupError) as error:
            await ConnectExternalIntegrationImpl(port, {SHEETS: integration}).execute(
                ConnectedExternalIntegrationRequest(SHEETS, PAYLOAD)
            )
        assert error.value.code == IntegrationSetupErrorCode.INVALID_CREDENTIALS
        port.activate.assert_not_called()

    @pytest.mark.asyncio
    async def test_unexpected_errors_are_wrapped(self):
        port = AsyncMock()
        integration = FakeOAuthIntegration(RuntimeError("boom"))
        with pytest.raises(IntegrationSetupError) as error:
            await ConnectExternalIntegrationImpl(port, {SHEETS: integration}).execute(
                ConnectedExternalIntegrationRequest(SHEETS, PAYLOAD)
            )
        assert error.value.code == IntegrationSetupErrorCode.UNKNOWN

    @pytest.mark.asyncio
    async def test_regular_integration_activates_without_link(self):
        port = AsyncMock()
        integration = FakeIntegration()
        result = await ConnectExternalIntegrationImpl(
            port, {SHEETS: integration}
        ).execute(ConnectedExternalIntegrationRequest(SHEETS, PAYLOAD, COMPLETION_URL))

        assert result.link is None
        assert integration.payloads == [PAYLOAD]
        port.activate.assert_awaited_once_with(SHEETS, PAYLOAD)


class TestCompleteExternalIntegrationConnection:
    @pytest.mark.asyncio
    async def test_activates_with_completed_payload(self):
        port = AsyncMock()
        integration = FakeOAuthIntegration()
        request = _complete_request(code="code")

        await CompleteExternalIntegrationConnectionImpl(
            port, {SHEETS: integration}
        ).execute(request)

        assert integration.completed == [request]
        port.activate.assert_awaited_once_with(SHEETS, COMPLETED_PAYLOAD)

    @pytest.mark.asyncio
    async def test_unregistered_integration_is_not_found(self):
        with pytest.raises(IntegrationNotFound):
            await CompleteExternalIntegrationConnectionImpl(AsyncMock(), {}).execute(
                _complete_request(code="code")
            )

    @pytest.mark.asyncio
    async def test_non_oauth_integration_is_not_found(self):
        port = AsyncMock()
        with pytest.raises(IntegrationNotFound):
            await CompleteExternalIntegrationConnectionImpl(
                port, {SHEETS: FakeIntegration()}
            ).execute(_complete_request(code="code"))
        port.activate.assert_not_called()

    @pytest.mark.asyncio
    async def test_setup_errors_are_propagated(self):
        port = AsyncMock()
        integration = FakeOAuthIntegration(
            IntegrationSetupError(IntegrationSetupErrorCode.AUTHORIZATION_DENIED)
        )
        with pytest.raises(IntegrationSetupError) as error:
            await CompleteExternalIntegrationConnectionImpl(
                port, {SHEETS: integration}
            ).execute(_complete_request(error="access_denied"))
        assert error.value.code == IntegrationSetupErrorCode.AUTHORIZATION_DENIED
        port.activate.assert_not_called()

    @pytest.mark.asyncio
    async def test_unexpected_errors_are_wrapped(self):
        port = AsyncMock()
        integration = FakeOAuthIntegration(RuntimeError("boom"))
        with pytest.raises(IntegrationSetupError) as error:
            await CompleteExternalIntegrationConnectionImpl(
                port, {SHEETS: integration}
            ).execute(_complete_request(code="code"))
        assert error.value.code == IntegrationSetupErrorCode.UNKNOWN
        port.activate.assert_not_called()
