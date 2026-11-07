import logging

from application.ports.connectable_integration import ConnectableIntegration
from application.ports.device_connectable_integration import (
    DeviceConnectableIntegration,
)
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.exception.exceptions import (
    IntegrationNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    DeviceAuthorizationStatus,
    ExternalIntegrationConnectionPoll,
    ExternalIntegrationConnectionStatus,
    ExternalIntegrationId,
    PollExternalIntegrationConnectionRequest,
)
from domain.use_cases.poll_external_integration_connection import (
    PollExternalIntegrationConnection,
)


class PollExternalIntegrationConnectionImpl(PollExternalIntegrationConnection):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        integrations: dict[ExternalIntegrationId, ConnectableIntegration],
    ):
        self._external_integration_port = external_integration_port
        self._integrations = integrations

        self._log = logging.getLogger(__name__)

    async def execute(
        self, request: PollExternalIntegrationConnectionRequest
    ) -> ExternalIntegrationConnectionPoll:
        integration = self._integrations.get(request.integration_id)
        if not isinstance(integration, DeviceConnectableIntegration):
            raise IntegrationNotFound()

        try:
            result = await integration.poll_device_authorization(request.flow_id)
            if result.status != DeviceAuthorizationStatus.AUTHORIZED:
                return ExternalIntegrationConnectionPoll(
                    ExternalIntegrationConnectionStatus.PENDING, result.interval
                )

            payload = result.payload or {}
            await integration.setup(payload)
        except IntegrationSetupError as e:
            raise e
        except Exception as e:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN) from e

        await self._external_integration_port.activate(request.integration_id, payload)
        return ExternalIntegrationConnectionPoll(
            ExternalIntegrationConnectionStatus.CONNECTED
        )
