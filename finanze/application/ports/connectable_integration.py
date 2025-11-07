import abc

from domain.external_integration import ExternalIntegrationPayload


class ConnectableIntegration(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def setup(self, payload: ExternalIntegrationPayload):
        raise NotImplementedError
