import abc

from domain.user_login import LoginRequest, LoginResult


class RegisterUser(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, login_request: LoginRequest) -> LoginResult:
        raise NotImplementedError
