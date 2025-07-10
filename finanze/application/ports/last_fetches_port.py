import abc
from uuid import UUID

from domain.entity import Entity, Feature
from domain.fetch_record import FetchRecord


class LastFetchesPort(metaclass=abc.ABCMeta):
    def get_by_entity_id(self, entity_id: UUID) -> list[FetchRecord]:
        raise NotImplementedError

    def get_grouped_by_entity(self, feature: Feature) -> dict[Entity, FetchRecord]:
        raise NotImplementedError

    def save(self, fetch_records: list[FetchRecord]):
        raise NotImplementedError
