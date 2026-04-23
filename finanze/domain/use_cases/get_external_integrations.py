import abc

from domain.external_integration import AvailableExternalIntegrations


class GetExternalIntegrations(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> AvailableExternalIntegrations:
        raise NotImplementedError
