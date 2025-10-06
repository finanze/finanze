import abc

from domain.global_position import UpdatePositionRequest


class UpdatePosition(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: UpdatePositionRequest):
        raise NotImplementedError
