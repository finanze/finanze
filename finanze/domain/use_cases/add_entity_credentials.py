import abc

from domain.entity_login import EntityLoginResult, EntityLoginRequest


class AddEntityCredentials(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    async def execute(self,
                      login_request: EntityLoginRequest) -> EntityLoginResult:
        raise NotImplementedError
