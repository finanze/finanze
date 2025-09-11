import abc

from domain.external_entity import (
    ConnectExternalEntityRequest,
    ExternalEntityConnectionResult,
)


class ConnectExternalEntity(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, request: ConnectExternalEntityRequest
    ) -> ExternalEntityConnectionResult:
        raise NotImplementedError
