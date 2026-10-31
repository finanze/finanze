import abc

from domain.external_integration import CompleteExternalIntegrationConnectionRequest


class CompleteExternalIntegrationConnection(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: CompleteExternalIntegrationConnectionRequest):
        raise NotImplementedError
