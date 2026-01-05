import abc

from domain.backup import ImportBackupRequest, BackupSyncResult


class ImportBackup(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: ImportBackupRequest) -> BackupSyncResult:
        raise NotImplementedError
