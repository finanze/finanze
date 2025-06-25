from datetime import datetime
from uuid import UUID

from domain.entity import Feature
from pydantic.dataclasses import dataclass


@dataclass
class FetchRecord:
    entity_id: UUID
    feature: Feature
    date: datetime
