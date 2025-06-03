import abc

from domain.login import LoginStatus


class GetLoginStatus(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self) -> LoginStatus:
        raise NotImplementedError
