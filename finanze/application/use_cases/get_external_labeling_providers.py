from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.external_tx_labeling_provider import (
    ExternalTxLabelingProvider,
)
from domain.external_integration import ExternalIntegrationId
from domain.external_labeling import (
    ExternalLabelingProviderDetails,
    ExternalLabelingProviders,
)
from domain.use_cases.get_external_labeling_providers import (
    GetExternalLabelingProviders,
)


class GetExternalLabelingProvidersImpl(GetExternalLabelingProviders):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        providers: dict[ExternalIntegrationId, ExternalTxLabelingProvider],
    ):
        self._external_integration_port = external_integration_port
        self._providers = providers

    async def execute(self) -> ExternalLabelingProviders:
        details = []
        for provider_id, provider in self._providers.items():
            payload = await self._external_integration_port.get_payload(provider_id)
            details.append(
                ExternalLabelingProviderDetails(
                    id=provider_id,
                    connected=payload is not None,
                    recommended_models=provider.get_recommended_models(),
                    upstream_providers=provider.supports_upstream_providers(),
                )
            )
        return ExternalLabelingProviders(providers=details)
