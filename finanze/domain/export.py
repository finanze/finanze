from enum import Enum
from typing import Optional

from domain.entity import Feature
from domain.global_position import ProductType
from domain.settings import TemplateConfig
from domain.template import ProcessorDataFilter, Template
from pydantic.dataclasses import dataclass


@dataclass
class SheetParams:
    range: str
    spreadsheet_id: str


class NumberFormat(str, Enum):
    EUROPEAN = "EUROPEAN"
    ENGLISH = "ENGLISH"


@dataclass
class TemplatedDataProcessorParams:
    template: Optional[Template]
    number_format: NumberFormat
    feature: Feature
    products: Optional[list[ProductType]]
    datetime_format: Optional[str]
    date_format: Optional[str]
    filters: Optional[list[ProcessorDataFilter]] = None


class FileFormat(str, Enum):
    CSV = "CSV"
    TSV = "TSV"
    XLSX = "XLSX"


@dataclass
class FileExportRequest:
    format: FileFormat
    number_format: NumberFormat
    feature: Feature
    data: list[ProductType] | None = None
    datetime_format: str | None = None
    date_format: str | None = None
    template: TemplateConfig | None = None


@dataclass
class FileExportResult:
    filename: str
    content_type: str
    data: bytes
    size: int
