import abc
from uuid import UUID


class CancelEntityLogin(abc.ABC):
    @abc.abstractmethod
    def execute(self, entity_id: UUID) -> None:
        raise NotImplementedError
