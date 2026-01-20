import abc

from domain.earnings_expenses import PendingFlow


class PendingFlowPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def save(self, flows: list[PendingFlow]):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_all(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_all(self) -> list[PendingFlow]:
        raise NotImplementedError
