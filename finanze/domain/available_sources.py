from enum import Enum

from pydantic.dataclasses import dataclass

from domain.financial_entity import NativeFinancialEntity


class FinancialEntityStatus(str, Enum):
    CONNECTED = ("CONNECTED",)
    DISCONNECTED = ("DISCONNECTED",)
    REQUIRES_LOGIN = ("REQUIRES_LOGIN",)


@dataclass(eq=False)
class AvailableFinancialEntity(NativeFinancialEntity):
    status: FinancialEntityStatus = FinancialEntityStatus.DISCONNECTED


@dataclass
class AvailableSources:
    virtual: bool
    entities: list[AvailableFinancialEntity]
