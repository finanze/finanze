from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.entity import Feature


class VirtualDataSource(str, Enum):
    SHEETS = "SHEETS"


@dataclass
class VirtualDataImport:
    import_id: UUID
    global_position_id: Optional[UUID]
    source: VirtualDataSource
    date: datetime
    feature: Optional[Feature]
    entity_id: Optional[UUID]
