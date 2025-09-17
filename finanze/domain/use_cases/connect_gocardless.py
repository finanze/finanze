import abc

from domain.external_integration import (
    GoCardlessIntegrationCredentials,
)


class ConnectGoCardless(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, data: GoCardlessIntegrationCredentials):
        raise NotImplementedError
