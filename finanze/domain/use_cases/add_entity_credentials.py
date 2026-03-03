import abc
from uuid import UUID

from domain.entity_login import EntityLoginResult, EntityLoginRequest


class AddEntityCredentials(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, login_request: EntityLoginRequest) -> EntityLoginResult:
        raise NotImplementedError

    @abc.abstractmethod
    def cancel_login(self, entity_id: UUID) -> None:
        raise NotImplementedError
