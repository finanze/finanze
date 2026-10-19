import abc
from uuid import UUID

from domain.global_position import UpdatePositionRequest


class UpdatePosition(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: UpdatePositionRequest) -> UUID:
        raise NotImplementedError
