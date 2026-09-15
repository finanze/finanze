import abc
from typing import Optional
from uuid import UUID

from domain.market_forecast import MarketForecastPnlResponse


class GetMarketForecastPnl(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self,
        entity_account_ids: Optional[list[UUID]] = None,
        interval: str = "all",
    ) -> MarketForecastPnlResponse:
        raise NotImplementedError
