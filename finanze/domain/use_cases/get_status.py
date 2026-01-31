import abc

from domain.status import GlobalStatus


class GetStatus(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> GlobalStatus:
        raise NotImplementedError
