import abc

from domain.real_estate import RealEstate


class ListRealEstate(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> list[RealEstate]:
        raise NotImplementedError
