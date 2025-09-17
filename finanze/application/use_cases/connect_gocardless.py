import logging

from application.ports.config_port import ConfigPort
from application.ports.connectable_integration import ConnectableIntegration
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.exception.exceptions import IntegrationSetupError, IntegrationSetupErrorCode
from domain.external_integration import (
    ExternalIntegrationId,
    ExternalIntegrationStatus,
    GoCardlessIntegrationCredentials,
)
from domain.settings import GoCardlessIntegrationConfig
from domain.use_cases.connect_gocardless import ConnectGoCardless


class ConnectGoCardlessImpl(ConnectGoCardless):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        config_port: ConfigPort,
        integration: ConnectableIntegration[GoCardlessIntegrationCredentials],
    ):
        self._external_integration_port = external_integration_port
        self._config_port = config_port
        self._integration = integration

        self._log = logging.getLogger(__name__)

    def execute(self, data: GoCardlessIntegrationCredentials):
        try:
            self._integration.setup(data)
        except IntegrationSetupError as e:
            raise e
        except Exception as e:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN) from e

        config = self._config_port.load()
        config.integrations.gocardless = GoCardlessIntegrationConfig(
            secret_id=data.secret_id, secret_key=data.secret_key
        )
        self._config_port.save(config)

        self._external_integration_port.update_status(
            ExternalIntegrationId.GOCARDLESS, ExternalIntegrationStatus.ON
        )
