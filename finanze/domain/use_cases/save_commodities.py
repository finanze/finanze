import abc

from domain.commodity import UpdateCommodityPosition


class SaveCommodities(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, commodity_position: UpdateCommodityPosition):
        raise NotImplementedError
