import abc
from typing import Optional
from uuid import UUID

from domain.earnings_expenses import PeriodicFlow


class PeriodicFlowPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def save(self, flow: PeriodicFlow) -> PeriodicFlow:
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, flow: PeriodicFlow):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, flow_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_all(self) -> list[PeriodicFlow]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_id(self, flow_id: UUID) -> Optional[PeriodicFlow]:
        raise NotImplementedError
