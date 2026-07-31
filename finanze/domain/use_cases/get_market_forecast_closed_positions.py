import abc
from typing import Optional
from uuid import UUID


class GetMarketForecastClosedPositions(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self,
        entity_account_ids: Optional[list[UUID]] = None,
    ) -> dict:
        raise NotImplementedError
