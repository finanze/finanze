import abc

from domain.external_entity import (
    DeleteExternalEntityRequest,
)


class DeleteExternalEntity(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: DeleteExternalEntityRequest):
        raise NotImplementedError
