import abc

from application.ports.connectable_integration import ConnectableIntegration
from domain.external_integration import GoogleIntegrationCredentials
from domain.user import User


class SheetsInitiator(
    ConnectableIntegration[GoogleIntegrationCredentials], metaclass=abc.ABCMeta
):
    @abc.abstractmethod
    def connect(self, user: User):
        raise NotImplementedError

    @abc.abstractmethod
    def disconnect(self):
        raise NotImplementedError
