from datetime import date
from enum import Enum
from typing import Annotated, Callable, Iterable, Optional, TypeVar
from uuid import UUID

from domain.global_position import ProductType
from domain.settings import SettingsSection
from pydantic import Field

from infrastructure.mcp.use_cases import McpUseCases

T = TypeVar("T")


class Granularity(str, Enum):
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"


EntityIds = Annotated[
    Optional[list[UUID]],
    Field(description="Filter by entity IDs (see list_entities). Omit for all."),
]
ProductTypes = Annotated[
    Optional[list[ProductType]],
    Field(description="Filter by product types. Omit for all."),
]
FromDate = Annotated[
    Optional[date], Field(description="Start date (YYYY-MM-DD), inclusive.")
]
ToDate = Annotated[
    Optional[date], Field(description="End date (YYYY-MM-DD), inclusive.")
]
CurrencyCode = Annotated[
    Optional[str],
    Field(
        description="ISO 4217 currency code. Defaults to the user's default currency.",
        min_length=3,
        max_length=3,
    ),
]
PointsGranularity = Annotated[
    Granularity,
    Field(
        description="Sampling of the returned points, keeping the last point of each period."
    ),
]
Page = Annotated[int, Field(description="Page number, starting at 1.", ge=1)]


async def resolve_currency(ucs: McpUseCases, currency: Optional[str]) -> str:
    if currency:
        return currency.upper()
    settings = await ucs.get_settings.execute({SettingsSection.GENERAL})
    return settings.general.defaultCurrency


def sample(
    items: Iterable[T], granularity: Granularity, get_date: Callable[[T], date]
) -> list[T]:
    items = list(items)
    if granularity == Granularity.DAY:
        return items

    def period(d: date):
        if granularity == Granularity.WEEK:
            return d.isocalendar()[:2]
        return d.year, d.month

    sampled: dict[tuple, T] = {}
    for item in items:
        sampled[period(get_date(item))] = item
    return list(sampled.values())
