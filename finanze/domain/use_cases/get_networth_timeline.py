import abc

from domain.networth_timeline import NetworthTimeline, NetworthTimelineQuery


class GetNetworthTimeline(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, query: NetworthTimelineQuery) -> NetworthTimeline:
        raise NotImplementedError
