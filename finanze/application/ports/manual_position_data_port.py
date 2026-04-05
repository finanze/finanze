import abc
from datetime import date
from uuid import UUID

from domain.dezimal import Dezimal
from domain.global_position import (
    ManualPositionData,
    ProductType,
)


class ManualPositionDataPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def save(self, entries: list[ManualPositionData]):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_trackable(self) -> list[ManualPositionData]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_trackable_loans(self) -> list[ManualPositionData]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_position_id(self, global_position_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def update_tracking_ref(
        self, entry_id: UUID, ref_outstanding: Dezimal, ref_date: date
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_position_id_and_type(
        self, global_position_id: UUID, product_type: ProductType
    ):
        raise NotImplementedError
