import abc
from typing import List

from domain.instrument import InstrumentDataRequest, InstrumentOverview


class GetInstruments(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: InstrumentDataRequest) -> List[InstrumentOverview]:  # noqa: D401
        raise NotImplementedError
