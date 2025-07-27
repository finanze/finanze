import abc
from uuid import UUID

from domain.earnings_expenses import PeriodicFlow


class PeriodicFlowPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, flow: PeriodicFlow):
        raise NotImplementedError

    @abc.abstractmethod
    def update(self, flow: PeriodicFlow):
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, flow_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> list[PeriodicFlow]:
        raise NotImplementedError
