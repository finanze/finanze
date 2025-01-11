from typing import Optional

from pydantic.dataclasses import dataclass

from domain.financial_entity import Entity, Feature


@dataclass
class PinDetails:
    positions: int


@dataclass
class AvailableSourceEntity:
    id: Entity
    features: list[Feature]
    name: str
    pin: Optional[PinDetails] = None


@dataclass
class AvailableSources:
    virtual: bool
    entities: list[AvailableSourceEntity]
