import abc

from domain.external_integration import (
    ConnectedExternalIntegrationRequest,
    ExternalIntegrationConnectionResult,
)


class ConnectExternalIntegration(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, request: ConnectedExternalIntegrationRequest
    ) -> ExternalIntegrationConnectionResult:
        raise NotImplementedError
