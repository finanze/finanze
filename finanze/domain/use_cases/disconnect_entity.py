import abc

from domain.entity_login import EntityDisconnectRequest


class DisconnectEntity(abc.ABC):

    @abc.abstractmethod
    def execute(self, request: EntityDisconnectRequest):
        raise NotImplementedError
