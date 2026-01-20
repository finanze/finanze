import abc

from domain.entity import Entity
from domain.importing import (
    ImportCandidate,
    PositionImportResult,
    TransactionsImportResult,
)


class TemplateParserPort(metaclass=abc.ABCMeta):
    async def global_positions(
        self, candidates: list[ImportCandidate], existing_entities: dict[str, Entity]
    ) -> PositionImportResult:
        raise NotImplementedError

    async def transactions(
        self, candidates: list[ImportCandidate], existing_entities: dict[str, Entity]
    ) -> TransactionsImportResult:
        raise NotImplementedError
