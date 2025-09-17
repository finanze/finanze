import abc

from domain.external_entity import (
    ExternalEntityCandidates,
    ExternalEntityCandidatesQuery,
)


class GetAvailableExternalEntities(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, request: ExternalEntityCandidatesQuery
    ) -> ExternalEntityCandidates:
        raise NotImplementedError
