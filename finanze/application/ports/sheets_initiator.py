import abc

from application.ports.oauth_connectable_integration import (
    OAuthConnectableIntegration,
)
from domain.user import User


class SheetsInitiator(OAuthConnectableIntegration, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def connect(self, user: User):
        raise NotImplementedError

    @abc.abstractmethod
    def disconnect(self):
        raise NotImplementedError
