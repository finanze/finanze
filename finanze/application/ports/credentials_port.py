import abc
from datetime import datetime
from typing import Optional
from uuid import UUID

from domain.native_entity import EntityCredentials, FinancialEntityCredentialsEntry


class CredentialsPort(metaclass=abc.ABCMeta):
    async def get(self, entity_id: UUID) -> Optional[EntityCredentials]:
        raise NotImplementedError

    async def get_available_entities(self) -> list[FinancialEntityCredentialsEntry]:
        raise NotImplementedError

    async def save(self, entity_id: UUID, credentials: EntityCredentials):
        raise NotImplementedError

    async def delete(self, entity_id: UUID):
        raise NotImplementedError

    async def update_last_usage(self, entity_id: UUID):
        raise NotImplementedError

    async def update_expiration(self, entity_id: UUID, expiration: Optional[datetime]):
        raise NotImplementedError
