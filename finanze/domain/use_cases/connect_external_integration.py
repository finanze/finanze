import abc

from domain.external_integration import (
    ConnectedExternalIntegrationRequest,
)


class ConnectExternalIntegration(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: ConnectedExternalIntegrationRequest):
        raise NotImplementedError
