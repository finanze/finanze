from typing import Optional

from domain.entity import Feature
from domain.global_position import ProductType
from domain.template import ProcessorDataFilter, Template
from pydantic.dataclasses import dataclass


@dataclass
class SheetParams:
    range: str
    spreadsheet_id: str


@dataclass
class TemplatedDataProcessorParams:
    template: Optional[Template]
    feature: Feature
    products: Optional[list[ProductType]]
    datetime_format: str
    date_format: str
    filters: Optional[list[ProcessorDataFilter]] = None
