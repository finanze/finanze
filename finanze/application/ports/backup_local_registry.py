import abc

from domain.backup import BackupsInfo, BackupInfo


class BackupLocalRegistry(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_info(self) -> BackupsInfo:
        raise NotImplementedError

    @abc.abstractmethod
    async def insert(self, entries: list[BackupInfo]):
        raise NotImplementedError
