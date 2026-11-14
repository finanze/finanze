import abc
from typing import Any

from domain.entity import Entity
from domain.importing import (
    ImportCandidate,
    PositionImportResult,
    TemplateFieldsSuggestion,
    TransactionsImportResult,
)
from domain.template import Template
from domain.template_fields import TemplateField


class TemplateParserPort(metaclass=abc.ABCMeta):
    async def global_positions(
        self, candidates: list[ImportCandidate], existing_entities: dict[str, Entity]
    ) -> PositionImportResult:
        raise NotImplementedError

    async def transactions(
        self, candidates: list[ImportCandidate], existing_entities: dict[str, Entity]
    ) -> TransactionsImportResult:
        raise NotImplementedError

    async def suggest_fields(
        self,
        table: list[list[Any]],
        fields: list[TemplateField],
        templates: list[Template],
    ) -> TemplateFieldsSuggestion:
        raise NotImplementedError
