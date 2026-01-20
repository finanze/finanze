import abc

from domain.backup import BackupSettings


class GetBackupSettings(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> BackupSettings:
        raise NotImplementedError
