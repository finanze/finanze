from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic.dataclasses import dataclass


class VirtualDataSource(str, Enum):
    SHEETS = "SHEETS"


@dataclass
class VirtualDataImport:
    import_id: UUID
    global_position_id: UUID
    source: VirtualDataSource
    date: datetime
