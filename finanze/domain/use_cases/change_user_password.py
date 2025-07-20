import abc

from domain.user_login import ChangePasswordRequest


class ChangeUserPassword(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, change_password_request: ChangePasswordRequest):
        raise NotImplementedError
