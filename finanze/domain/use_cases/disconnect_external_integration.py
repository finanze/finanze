import abc

from domain.external_integration import DisconnectedExternalIntegrationRequest


class DisconnectExternalIntegration(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, request: DisconnectedExternalIntegrationRequest):
        raise NotImplementedError
