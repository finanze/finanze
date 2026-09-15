import abc

from domain.gains_timeline import GainsTimeline, GainsTimelineQuery


class GetGainsTimeline(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, query: GainsTimelineQuery) -> GainsTimeline:
        raise NotImplementedError
