import abc

from domain.user_login import LoginRequest


class UserLogin(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def execute(self, login_request: LoginRequest):
        raise NotImplementedError
