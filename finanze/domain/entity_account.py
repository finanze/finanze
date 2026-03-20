from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass


@dataclass
class EntityAccount:
    id: UUID
    entity_id: UUID
    created_at: datetime
    name: Optional[str] = None
    deleted_at: Optional[datetime] = None
