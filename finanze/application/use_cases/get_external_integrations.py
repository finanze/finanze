from application.ports.external_integration_port import ExternalIntegrationPort
from domain.external_integration import AvailableExternalIntegrations
from domain.use_cases.get_external_integrations import GetExternalIntegrations


class GetExternalIntegrationsImpl(GetExternalIntegrations):
    def __init__(self, external_integration_port: ExternalIntegrationPort):
        self._external_integration_port = external_integration_port

    def execute(self) -> AvailableExternalIntegrations:
        return AvailableExternalIntegrations(self._external_integration_port.get_all())
