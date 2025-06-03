import abc

from domain.global_position import EntitiesPosition, PositionQueryRequest


class GetPosition(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, query: PositionQueryRequest) -> EntitiesPosition:
        pass
