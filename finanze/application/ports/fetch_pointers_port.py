import abc
from uuid import UUID

from domain.fetch_pointer import FetchPointer


class FetchPointersPort(metaclass=abc.ABCMeta):
    async def get_by_entity_account_id(
        self, entity_account_id: UUID
    ) -> list[FetchPointer]:
        raise NotImplementedError

    async def save(self, fetch_pointers: list[FetchPointer]):
        raise NotImplementedError

    async def delete_by_entity_account_id(self, entity_account_id: UUID):
        raise NotImplementedError
