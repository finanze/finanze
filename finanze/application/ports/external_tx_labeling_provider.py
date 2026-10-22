import abc

from domain.external_integration import ExternalIntegrationPayload
from domain.external_labeling import (
    ExternalLabelingModel,
    ExternalLabelingRequest,
    ExternalLabelSuggestion,
)


class ExternalTxLabelingProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def label(
        self,
        request: ExternalLabelingRequest,
        credentials: ExternalIntegrationPayload,
    ) -> list[ExternalLabelSuggestion]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_recommended_models(self) -> list[ExternalLabelingModel]:
        raise NotImplementedError

    def supports_upstream_providers(self) -> bool:
        return False

    def custom_models(self) -> bool:
        return True

    def dynamic_models(self) -> bool:
        return False

    async def list_models(
        self, credentials: ExternalIntegrationPayload
    ) -> list[ExternalLabelingModel]:
        return []
