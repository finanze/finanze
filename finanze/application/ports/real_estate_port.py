import abc
from typing import Optional
from uuid import UUID

from domain.real_estate import RealEstate


class RealEstatePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def insert(self, real_estate: RealEstate) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, real_estate: RealEstate) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, real_estate_id: UUID) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_id(self, real_estate_id: UUID) -> Optional[RealEstate]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_all(self) -> list[RealEstate]:
        raise NotImplementedError
