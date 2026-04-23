import abc

from domain.backup import UploadBackupRequest, BackupSyncResult


class UploadBackup(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: UploadBackupRequest) -> BackupSyncResult:
        raise NotImplementedError
