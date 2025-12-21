import abc

from domain.backup import ImportBackupRequest, BackupSyncResult


class ImportBackup(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, request: ImportBackupRequest) -> BackupSyncResult:
        raise NotImplementedError
