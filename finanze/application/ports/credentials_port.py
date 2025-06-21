import abc
from datetime import datetime
from typing import Optional
from uuid import UUID

from domain.entity import EntityCredentials, FinancialEntityCredentialsEntry


class CredentialsPort(metaclass=abc.ABCMeta):
    def get(self, entity_id: UUID) -> Optional[EntityCredentials]:
        raise NotImplementedError

    def get_available_entities(self) -> list[FinancialEntityCredentialsEntry]:
        raise NotImplementedError

    def save(self, entity_id: UUID, credentials: EntityCredentials):
        raise NotImplementedError

    def delete(self, entity_id: UUID):
        raise NotImplementedError

    def update_last_usage(self, entity_id: UUID):
        raise NotImplementedError

    def update_expiration(self, entity_id: UUID, expiration: Optional[datetime]):
        raise NotImplementedError
