from pydantic.dataclasses import dataclass

from domain.financial_entity import NativeFinancialEntity


@dataclass(eq=False)
class AvailableFinancialEntity(NativeFinancialEntity):
    setup: bool = False


@dataclass
class AvailableSources:
    virtual: bool
    entities: list[AvailableFinancialEntity]
