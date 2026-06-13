import abc
from datetime import date
from typing import Optional

from domain.networth_timeline import (
    MortgageValuation,
    NetworthTimelinePoint,
    NetworthTimelineState,
    PositionSnapshot,
)


class NetworthTimelinePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_points(
        self, from_date: Optional[date], to_date: Optional[date]
    ) -> list[NetworthTimelinePoint]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_state(self) -> NetworthTimelineState:
        raise NotImplementedError

    @abc.abstractmethod
    async def persist(
        self,
        points: list[NetworthTimelinePoint],
        currency: str,
        state: NetworthTimelineState,
        wipe: bool,
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_position_snapshots(
        self, excluded_entity_ids: list[str]
    ) -> list[PositionSnapshot]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_mortgage_valuations(
        self, loan_refs: list[str]
    ) -> list[MortgageValuation]:
        raise NotImplementedError
