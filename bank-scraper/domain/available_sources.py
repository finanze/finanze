from pydantic.dataclasses import dataclass

from domain.financial_entity import FinancialEntity


@dataclass
class AvailableSources:
    virtual: bool
    entities: list[FinancialEntity]
