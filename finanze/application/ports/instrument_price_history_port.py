import abc
from datetime import date

from domain.instrument_history import InstrumentPricePoint, InstrumentSplit


class InstrumentPriceHistoryPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_history(
        self, instrument_key: str, from_date: date, to_date: date
    ) -> list[InstrumentPricePoint]:
        raise NotImplementedError

    @abc.abstractmethod
    async def upsert(
        self,
        instrument_key: str,
        points: list[InstrumentPricePoint],
        source: str,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_covered_range(self, instrument_key: str) -> tuple[date, date] | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_resolved_symbol(self, instrument_key: str) -> tuple[str, str] | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def save_resolved_symbol(
        self, instrument_key: str, symbol: str, source: str
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_splits(self, instrument_key: str) -> list[InstrumentSplit]:
        raise NotImplementedError

    @abc.abstractmethod
    async def save_splits(
        self, instrument_key: str, splits: list[InstrumentSplit]
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def is_splits_checked(self, instrument_key: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def mark_splits_checked(self, instrument_key: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_empty_gap_days(
        self, instrument_key: str, from_date: date, to_date: date
    ) -> set[date]:
        raise NotImplementedError

    @abc.abstractmethod
    async def mark_empty_gap_days(self, instrument_key: str, days: list[date]) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def is_no_result(self, instrument_key: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def mark_no_result(self, instrument_key: str) -> None:
        raise NotImplementedError
