import abc
from dataclasses import dataclass, field
from typing import Any

from domain.entity_login import EntityLoginParams


@dataclass
class MarketForecastAccountData:
    wallet_address: str
    profile: dict[str, Any] | None = None
    open_positions: list[dict[str, Any]] = field(default_factory=list)
    closed_positions: list[dict[str, Any]] = field(default_factory=list)
    pnl_history: list[dict[str, Any]] = field(default_factory=list)


class MarketForecastProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_open_positions(
        self, login_params: EntityLoginParams
    ) -> MarketForecastAccountData | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_closed_positions(
        self, login_params: EntityLoginParams
    ) -> MarketForecastAccountData | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_pnl_history(
        self, login_params: EntityLoginParams, interval: str = "all"
    ) -> MarketForecastAccountData | None:
        raise NotImplementedError
