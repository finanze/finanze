from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.external_tx_labeling_provider import (
    ExternalTxLabelingProvider,
)
from domain.exception.exceptions import (
    ExternalIntegrationRequired,
    IntegrationNotFound,
)
from domain.external_integration import ExternalIntegrationId
from domain.external_labeling import ExternalLabelingModels
from domain.use_cases.get_external_labeling_models import GetExternalLabelingModels


class GetExternalLabelingModelsImpl(GetExternalLabelingModels):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        providers: dict[ExternalIntegrationId, ExternalTxLabelingProvider],
    ):
        self._external_integration_port = external_integration_port
        self._providers = providers

    async def execute(self, provider_id: str) -> ExternalLabelingModels:
        try:
            integration_id = ExternalIntegrationId(provider_id)
        except ValueError:
            raise IntegrationNotFound()
        provider = self._providers.get(integration_id)
        if provider is None:
            raise IntegrationNotFound()
        if not provider.dynamic_models():
            return ExternalLabelingModels(models=[])

        credentials = await self._external_integration_port.get_payload(integration_id)
        if credentials is None:
            raise ExternalIntegrationRequired([integration_id])

        return ExternalLabelingModels(models=await provider.list_models(credentials))
