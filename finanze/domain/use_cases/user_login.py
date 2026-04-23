import abc

from domain.user_login import LoginRequest


class UserLogin(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, login_request: LoginRequest):
        raise NotImplementedError
