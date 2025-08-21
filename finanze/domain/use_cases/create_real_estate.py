import abc

from domain.real_estate import CreateRealEstateRequest


class CreateRealEstate(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: CreateRealEstateRequest):
        raise NotImplementedError
