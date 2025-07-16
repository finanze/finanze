import abc

from domain.external_integration import (
    EtherscanIntegrationData,
)


class ConnectEtherscan(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, data: EtherscanIntegrationData):
        raise NotImplementedError
