import abc

from domain.login import LoginResult, LoginRequest


class AddEntityCredentials(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    async def execute(self,
                      login_request: LoginRequest) -> LoginResult:
        raise NotImplementedError
