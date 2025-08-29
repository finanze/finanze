import abc

from domain.real_estate import UpdateRealEstateRequest


class UpdateRealEstate(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: UpdateRealEstateRequest):
        raise NotImplementedError
