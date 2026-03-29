from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.entity import Feature
from pydantic.dataclasses import dataclass


@dataclass
class FetchRecord:
    entity_id: UUID
    feature: Feature
    date: datetime
    entity_account_id: Optional[UUID] = None


class DataSource(str, Enum):
    SHEETS = "SHEETS"
    MANUAL = "MANUAL"
    REAL = "REAL"
