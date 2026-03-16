import abc
from uuid import UUID

from domain.fetch_record import FetchRecord


class LastFetchesPort(metaclass=abc.ABCMeta):
    async def get_by_entity_id(self, entity_id: UUID) -> list[FetchRecord]:
        raise NotImplementedError

    async def save(self, fetch_records: list[FetchRecord]):
        raise NotImplementedError
