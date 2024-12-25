from dataclasses import dataclass

from domain.financial_entity import Entity, Feature


@dataclass
class AvailableSourceEntity:
    entity: Entity
    features: list[Feature]


@dataclass
class AvailableSources:
    virtual: bool
    entities: list[AvailableSourceEntity]
