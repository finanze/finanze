import abc

from domain.real_estate import DeleteRealEstateRequest


class DeleteRealEstate(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, delete_request: DeleteRealEstateRequest):
        raise NotImplementedError
