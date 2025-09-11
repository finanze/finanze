import logging

from application.ports.config_port import ConfigPort
from application.ports.connectable_integration import ConnectableIntegration
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.exception.exceptions import IntegrationSetupError, IntegrationSetupErrorCode
from domain.external_integration import (
    EtherscanIntegrationData,
    ExternalIntegrationId,
    ExternalIntegrationStatus,
)
from domain.settings import EtherscanIntegrationConfig
from domain.use_cases.connect_etherscan import ConnectEtherscan


class ConnectEtherscanImpl(ConnectEtherscan):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        config_port: ConfigPort,
        integration: ConnectableIntegration[EtherscanIntegrationData],
    ):
        self._external_integration_port = external_integration_port
        self._config_port = config_port
        self._integration = integration

        self._log = logging.getLogger(__name__)

    def execute(self, data: EtherscanIntegrationData):
        try:
            self._integration.setup(data)
        except IntegrationSetupError as e:
            raise e
        except Exception as e:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN) from e

        config = self._config_port.load()
        config.integrations.etherscan = EtherscanIntegrationConfig(api_key=data.api_key)
        self._config_port.save(config)

        self._external_integration_port.update_status(
            ExternalIntegrationId.ETHERSCAN, ExternalIntegrationStatus.ON
        )
