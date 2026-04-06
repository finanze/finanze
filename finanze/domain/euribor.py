from dataclasses import field

from pydantic.dataclasses import dataclass

from domain.dezimal import Dezimal


@dataclass
class EuriborRate:
    period: str
    rate: Dezimal


@dataclass
class EuriborHistory:
    rates: list[EuriborRate] = field(default_factory=list)
