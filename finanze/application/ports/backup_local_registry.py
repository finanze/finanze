import abc

from domain.backup import BackupsInfo, BackupInfo


class BackupLocalRegistry(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_info(self) -> BackupsInfo:
        raise NotImplementedError

    @abc.abstractmethod
    def insert(self, entries: list[BackupInfo]):
        raise NotImplementedError
