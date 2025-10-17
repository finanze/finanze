import abc
from typing import Optional

from domain.instrument import (
    InstrumentDataRequest,
    InstrumentInfo,
    InstrumentOverview,
)


class InstrumentInfoProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def lookup(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_info(self, request: InstrumentDataRequest) -> Optional[InstrumentInfo]:
        raise NotImplementedError
