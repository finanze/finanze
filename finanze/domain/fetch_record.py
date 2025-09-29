from datetime import datetime
from enum import Enum
from uuid import UUID

from domain.entity import Feature
from pydantic.dataclasses import dataclass


@dataclass
class FetchRecord:
    entity_id: UUID
    feature: Feature
    date: datetime


class DataSource(str, Enum):
    SHEETS = "SHEETS"
    MANUAL = "MANUAL"
    REAL = "REAL"
