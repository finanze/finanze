from dataclasses import field
from datetime import date
from uuid import UUID

from pydantic.dataclasses import dataclass


@dataclass
class FetchPointer:
    entity_id: UUID
    entity_account_id: UUID
    key: str
    threshold: date


@dataclass
class FetchPointerContext:
    entity_id: UUID
    entity_account_id: UUID
    pointers: dict[str, FetchPointer] = field(default_factory=dict)
