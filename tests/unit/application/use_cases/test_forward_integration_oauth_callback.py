from unittest.mock import AsyncMock

import pytest
from application.ports.connectable_integration import ConnectableIntegration
from application.ports.oauth_connectable_integration import (
    OAuthConnectableIntegration,
)
from application.use_cases.disconnect_external_integration import (
    DisconnectExternalIntegrationImpl,
)
from application.use_cases.forward_integration_oauth_callback import (
    ForwardIntegrationOAuthCallbackImpl,
)
from domain.external_integration import (
    DisconnectedExternalIntegrationRequest,
    ExternalIntegrationId,
    ForwardIntegrationOAuthCallbackRequest,
)

CHATGPT = ExternalIntegrationId.CHATGPT
WEB_DESTINATION = (
    "http://localhost:8080/?integration_oauth=CHATGPT"
    "#/entities?tab=providers&focus=CHATGPT"
)
DEEP_LINK = "finanze://integration/complete?integration_oauth=CHATGPT"


class FakeLoopbackIntegration(OAuthConnectableIntegration):
    def __init__(self, destinations: dict[str, str]):
        self.destinations = destinations
        self.teardowns = []

    async def start_authorization(self, payload, completion_url):
        return "https://auth.example/authorize"

    async def complete_authorization(self, request):
        return {}

    async def callback_destination(self, state):
        return self.destinations.get(state)

    async def teardown(self, payload=None):
        self.teardowns.append(payload)


class FakeIntegration(ConnectableIntegration):
    async def setup(self, payload):
        pass


def _forward(destinations: dict[str, str], **kwargs):
    return ForwardIntegrationOAuthCallbackImpl(
        {
            ExternalIntegrationId.ETHERSCAN: FakeIntegration(),
            CHATGPT: FakeLoopbackIntegration(destinations),
        }
    ).execute(ForwardIntegrationOAuthCallbackRequest(**kwargs))


class TestForwardIntegrationOAuthCallback:
    @pytest.mark.asyncio
    async def test_adds_the_callback_before_the_web_fragment(self):
        destination = await _forward(
            {"state-1": WEB_DESTINATION},
            state="state-1",
            code="auth code",
            client_id="oaiapp_1",
        )

        assert destination == (
            "http://localhost:8080/?integration_oauth=CHATGPT&state=state-1"
            "&code=auth+code&client_id=oaiapp_1#/entities?tab=providers&focus=CHATGPT"
        )

    @pytest.mark.asyncio
    async def test_forwards_errors_to_the_deep_link(self):
        destination = await _forward(
            {"state-1": DEEP_LINK}, state="state-1", error="access_denied"
        )

        assert destination == (
            "finanze://integration/complete?integration_oauth=CHATGPT"
            "&state=state-1&error=access_denied"
        )

    @pytest.mark.asyncio
    async def test_callback_values_cannot_override_the_destination_params(self):
        destination = await _forward(
            {"state-1": DEEP_LINK + "&state=forged"}, state="state-1", code="c"
        )

        assert destination.count("state=") == 1
        assert "state=state-1" in destination

    @pytest.mark.asyncio
    async def test_unknown_state_is_not_forwarded(self):
        assert await _forward({"state-1": DEEP_LINK}, state="other") is None


class TestDisconnectTeardownPayload:
    @pytest.mark.asyncio
    async def test_teardown_receives_the_stored_credentials(self):
        port = AsyncMock()
        port.get_payload.return_value = {"refresh_token": "refresh"}
        integration = FakeLoopbackIntegration({})

        await DisconnectExternalIntegrationImpl(port, {CHATGPT: integration}).execute(
            DisconnectedExternalIntegrationRequest(CHATGPT)
        )

        port.get_payload.assert_awaited_once_with(CHATGPT, include_expired=True)
        port.deactivate.assert_awaited_once_with(CHATGPT)
        assert integration.teardowns == [{"refresh_token": "refresh"}]

    @pytest.mark.asyncio
    async def test_non_connectable_integrations_skip_the_payload_lookup(self):
        port = AsyncMock()

        await DisconnectExternalIntegrationImpl(
            port, {ExternalIntegrationId.ETHERSCAN: True}
        ).execute(
            DisconnectedExternalIntegrationRequest(ExternalIntegrationId.ETHERSCAN)
        )

        port.get_payload.assert_not_called()
        port.deactivate.assert_awaited_once_with(ExternalIntegrationId.ETHERSCAN)
