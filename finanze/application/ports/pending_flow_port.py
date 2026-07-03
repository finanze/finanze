import abc
from typing import Optional
from uuid import UUID

from domain.earnings_expenses import PendingFlow


class PendingFlowPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def save(self, flow: PendingFlow) -> PendingFlow:
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, flow: PendingFlow):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, flow_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_all(self) -> list[PendingFlow]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_id(self, flow_id: UUID) -> Optional[PendingFlow]:
        raise NotImplementedError
