import abc

from domain.entity_login import EntityLoginParams
from domain.market_forecast import (
    MarketForecastClosedPositionsAccountData,
    MarketForecastPnlAccountData,
)


class MarketForecastProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_closed_positions(
        self, login_params: EntityLoginParams
    ) -> MarketForecastClosedPositionsAccountData | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_pnl_history(
        self, login_params: EntityLoginParams, interval: str = "all"
    ) -> MarketForecastPnlAccountData | None:
        raise NotImplementedError
