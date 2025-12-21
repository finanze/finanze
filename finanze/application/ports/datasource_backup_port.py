import abc
from datetime import datetime


class Backupable(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def export(self) -> bytes:
        raise NotImplementedError

    @abc.abstractmethod
    def import_data(self, data: bytes):
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_updated(self) -> datetime:
        raise NotImplementedError
