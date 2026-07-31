import abc
from typing import Optional
from uuid import UUID


class GetMarketForecastPnl(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self,
        entity_account_ids: Optional[list[UUID]] = None,
        interval: str = "all",
    ) -> dict:
        raise NotImplementedError
