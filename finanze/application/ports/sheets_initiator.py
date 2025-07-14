import abc

from domain.external_integration import GoogleIntegrationCredentials
from domain.user import User


class SheetsInitiator(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def connect(self, user: User):
        raise NotImplementedError

    @abc.abstractmethod
    def disconnect(self):
        raise NotImplementedError

    @abc.abstractmethod
    def setup_credentials(self, credentials: GoogleIntegrationCredentials):
        raise NotImplementedError
