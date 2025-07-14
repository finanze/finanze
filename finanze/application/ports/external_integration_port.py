import abc

from domain.external_integration import (
    ExternalIntegration,
    ExternalIntegrationId,
    ExternalIntegrationStatus,
)


class ExternalIntegrationPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update_status(
        self, integration: ExternalIntegrationId, status: ExternalIntegrationStatus
    ):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> list[ExternalIntegration]:
        raise NotImplementedError
