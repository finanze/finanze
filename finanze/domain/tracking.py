from dataclasses import field
from uuid import UUID

from pydantic.dataclasses import dataclass


@dataclass
class UpdateTrackedResult:
    had_tracked: bool
    changed_entities: list[UUID] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.changed_entities)
