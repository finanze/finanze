import logging

from application.ports.config_port import ConfigPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.sheets_initiator import SheetsInitiator
from domain.exception.exceptions import IntegrationSetupError
from domain.external_integration import (
    ExternalIntegrationId,
    ExternalIntegrationStatus,
    GoogleIntegrationCredentials,
)
from domain.settings import GoogleCredentials, SheetsIntegrationConfig
from domain.use_cases.connect_google import ConnectGoogle


class ConnectGoogleImpl(ConnectGoogle):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        config_port: ConfigPort,
        sheets_initiator: SheetsInitiator,
    ):
        self._external_integration_port = external_integration_port
        self._config_port = config_port
        self._sheets_initiator = sheets_initiator

        self._log = logging.getLogger(__name__)

    def execute(self, credentials: GoogleIntegrationCredentials):
        try:
            self._sheets_initiator.setup(credentials)
        except Exception as e:
            raise IntegrationSetupError(e)

        config = self._config_port.load()
        config.integrations.sheets = SheetsIntegrationConfig(
            GoogleCredentials(
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
            )
        )
        self._config_port.save(config)

        self._external_integration_port.update_status(
            ExternalIntegrationId.GOOGLE_SHEETS, ExternalIntegrationStatus.ON
        )
