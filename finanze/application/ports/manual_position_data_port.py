import abc
from uuid import UUID

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
    async def delete_by_position_id_and_type(
        self, global_position_id: UUID, product_type: ProductType
    ):
        raise NotImplementedError
