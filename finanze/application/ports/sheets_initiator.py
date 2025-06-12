import abc

from domain.user import User


class SheetsInitiator(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def connect(self, user: User):
        raise NotImplementedError

    @abc.abstractmethod
    def disconnect(self):
        raise NotImplementedError
