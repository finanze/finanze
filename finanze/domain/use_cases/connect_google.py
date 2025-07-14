import abc

from domain.external_integration import GoogleIntegrationCredentials


class ConnectGoogle(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, credentials: GoogleIntegrationCredentials):
        raise NotImplementedError
