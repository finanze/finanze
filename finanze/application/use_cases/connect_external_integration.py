import logging

from application.ports.connectable_integration import ConnectableIntegration
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.oauth_connectable_integration import (
    OAuthConnectableIntegration,
)
from domain.exception.exceptions import (
    IntegrationNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    EXTERNAL_INTEGRATION_OPTIONAL_FIELDS,
    EXTERNAL_INTEGRATION_PAYLOAD_SCHEMAS,
    ConnectedExternalIntegrationRequest,
    ExternalIntegrationConnectionResult,
    ExternalIntegrationId,
)
from domain.use_cases.connect_external_integration import ConnectExternalIntegration


class ConnectExternalIntegrationImpl(ConnectExternalIntegration):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        integrations: dict[ExternalIntegrationId, ConnectableIntegration],
    ):
        self._external_integration_port = external_integration_port
        self._integrations = integrations

        self._log = logging.getLogger(__name__)

    async def execute(
        self, request: ConnectedExternalIntegrationRequest
    ) -> ExternalIntegrationConnectionResult:
        integration = self._integrations.get(request.integration_id)
        if integration is None:
            raise IntegrationNotFound()

        payload_schema = EXTERNAL_INTEGRATION_PAYLOAD_SCHEMAS[request.integration_id]
        optional_fields = EXTERNAL_INTEGRATION_OPTIONAL_FIELDS.get(
            request.integration_id, set()
        )
        payload = {
            key: value
            for key, value in request.payload.items()
            if key not in optional_fields or (isinstance(value, str) and value.strip())
        }

        for key in payload_schema:
            if key not in optional_fields and key not in payload:
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.INVALID_CREDENTIALS
                )

        try:
            if isinstance(integration, OAuthConnectableIntegration):
                link = await integration.start_authorization(
                    payload, request.completion_url
                )
                return ExternalIntegrationConnectionResult(link=link)

            await integration.setup(payload)
        except IntegrationSetupError as e:
            raise e
        except Exception as e:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN) from e

        await self._external_integration_port.activate(request.integration_id, payload)
        return ExternalIntegrationConnectionResult()
