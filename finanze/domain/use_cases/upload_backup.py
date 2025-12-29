import abc

from domain.backup import UploadBackupRequest, BackupSyncResult


class UploadBackup(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, request: UploadBackupRequest) -> BackupSyncResult:
        raise NotImplementedError
