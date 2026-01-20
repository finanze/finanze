import abc
import datetime
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.fetch_record import DataSource
from domain.global_position import (
    FundDetail,
    GlobalPosition,
    PositionQueryRequest,
    ProductType,
    StockDetail,
)


class PositionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def save(self, position: GlobalPosition):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_last_grouped_by_entity(
        self, query: Optional[PositionQueryRequest] = None
    ) -> dict[Entity, GlobalPosition]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_position_for_date(
        self, entity_id: UUID, date: datetime.date, source: DataSource
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_id(self, position_id: UUID) -> Optional[GlobalPosition]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_id(self, position_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_stock_detail(self, entry_id: UUID) -> Optional[StockDetail]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_fund_detail(self, entry_id: UUID) -> Optional[FundDetail]:
        raise NotImplementedError

    @abc.abstractmethod
    async def update_market_value(
        self, entry_id: UUID, product_type: ProductType, market_value: Dezimal
    ):
        raise NotImplementedError
