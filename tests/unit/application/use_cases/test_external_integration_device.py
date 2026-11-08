from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from application.ports.connectable_integration import ConnectableIntegration
from application.ports.device_connectable_integration import (
    DeviceConnectableIntegration,
)
from application.use_cases.connect_external_integration import (
    ConnectExternalIntegrationImpl,
)
from application.use_cases.poll_external_integration_connection import (
    PollExternalIntegrationConnectionImpl,
)
from dateutil.tz import tzlocal
from domain.exception.exceptions import (
    IntegrationNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    ConnectedExternalIntegrationRequest,
    DeviceAuthorizationPollResult,
    DeviceAuthorizationStatus,
    ExternalIntegrationConnectionStatus,
    ExternalIntegrationDeviceAuthorization,
    ExternalIntegrationId,
    PollExternalIntegrationConnectionRequest,
)

COPILOT = ExternalIntegrationId.GITHUB_COPILOT
TOKEN_PAYLOAD = {"access_token": "gho_token", "token_type": "bearer"}
AUTHORIZATION = ExternalIntegrationDeviceAuthorization(
    flow_id="flow",
    user_code="ABCD-1234",
    verification_uri="https://github.com/login/device",
    expires_at=datetime.now(tzlocal()) + timedelta(minutes=15),
    interval=5,
)


class FakeDeviceIntegration(DeviceConnectableIntegration):
    def __init__(
        self,
        poll_results: list[DeviceAuthorizationPollResult] | None = None,
        poll_error: Exception | None = None,
        setup_error: Exception | None = None,
    ):
        self.poll_results = list(poll_results or [])
        self.poll_error = poll_error
        self.setup_error = setup_error
        self.started = []
        self.polled = []
        self.setups = []

    async def start_device_authorization(self, payload):
        self.started.append(payload)
        return AUTHORIZATION

    async def poll_device_authorization(self, flow_id):
        self.polled.append(flow_id)
        if self.poll_error:
            raise self.poll_error
        return self.poll_results.pop(0)

    async def setup(self, payload):
        self.setups.append(payload)
        if self.setup_error:
            raise self.setup_error


class FakeIntegration(ConnectableIntegration):
    async def setup(self, payload):
        pass


def _pending(interval=5):
    return DeviceAuthorizationPollResult(DeviceAuthorizationStatus.PENDING, interval)


def _authorized():
    return DeviceAuthorizationPollResult(
        DeviceAuthorizationStatus.AUTHORIZED, 5, TOKEN_PAYLOAD
    )


async def _poll(port, integration, flow_id="flow"):
    return await PollExternalIntegrationConnectionImpl(
        port, {COPILOT: integration}
    ).execute(PollExternalIntegrationConnectionRequest(COPILOT, flow_id))


class TestConnectDeviceIntegration:
    @pytest.mark.asyncio
    async def test_returns_device_authorization_without_activating(self):
        port = AsyncMock()
        integration = FakeDeviceIntegration()

        result = await ConnectExternalIntegrationImpl(
            port, {COPILOT: integration}
        ).execute(ConnectedExternalIntegrationRequest(COPILOT, {}))

        assert result.device == AUTHORIZATION
        assert result.link is None
        assert integration.started == [{}]
        assert integration.setups == []
        port.activate.assert_not_called()


class TestPollExternalIntegrationConnection:
    @pytest.mark.asyncio
    async def test_pending_returns_interval_without_activating(self):
        port = AsyncMock()
        integration = FakeDeviceIntegration([_pending(10)])

        result = await _poll(port, integration)

        assert result.status == ExternalIntegrationConnectionStatus.PENDING
        assert result.interval == 10
        assert integration.polled == ["flow"]
        assert integration.setups == []
        port.activate.assert_not_called()

    @pytest.mark.asyncio
    async def test_authorized_validates_and_activates(self):
        port = AsyncMock()
        integration = FakeDeviceIntegration([_authorized()])

        result = await _poll(port, integration)

        assert result.status == ExternalIntegrationConnectionStatus.CONNECTED
        assert result.interval is None
        assert integration.setups == [TOKEN_PAYLOAD]
        port.activate.assert_awaited_once_with(COPILOT, TOKEN_PAYLOAD)

    @pytest.mark.asyncio
    async def test_failed_validation_does_not_activate(self):
        port = AsyncMock()
        integration = FakeDeviceIntegration(
            [_authorized()],
            setup_error=IntegrationSetupError(IntegrationSetupErrorCode.NOT_ENTITLED),
        )

        with pytest.raises(IntegrationSetupError) as error:
            await _poll(port, integration)

        assert error.value.code == IntegrationSetupErrorCode.NOT_ENTITLED
        port.activate.assert_not_called()

    @pytest.mark.asyncio
    async def test_authorization_errors_are_propagated(self):
        port = AsyncMock()
        integration = FakeDeviceIntegration(
            poll_error=IntegrationSetupError(
                IntegrationSetupErrorCode.AUTHORIZATION_DENIED
            )
        )

        with pytest.raises(IntegrationSetupError) as error:
            await _poll(port, integration)

        assert error.value.code == IntegrationSetupErrorCode.AUTHORIZATION_DENIED

    @pytest.mark.asyncio
    async def test_unexpected_errors_are_wrapped(self):
        port = AsyncMock()
        integration = FakeDeviceIntegration(poll_error=RuntimeError("boom"))

        with pytest.raises(IntegrationSetupError) as error:
            await _poll(port, integration)

        assert error.value.code == IntegrationSetupErrorCode.UNKNOWN

    @pytest.mark.parametrize("integrations", [{}, {COPILOT: FakeIntegration()}])
    @pytest.mark.asyncio
    async def test_non_device_integrations_are_not_found(self, integrations):
        with pytest.raises(IntegrationNotFound):
            await PollExternalIntegrationConnectionImpl(
                AsyncMock(), integrations
            ).execute(PollExternalIntegrationConnectionRequest(COPILOT, "flow"))
