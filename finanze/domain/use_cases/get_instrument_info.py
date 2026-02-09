import abc
from typing import Optional

from domain.instrument import InstrumentDataRequest, InstrumentInfo


class GetInstrumentInfo(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: InstrumentDataRequest) -> Optional[InstrumentInfo]:  # noqa: D401
        raise NotImplementedError
