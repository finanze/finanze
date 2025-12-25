import abc

from domain.backup import (
    BackupPieces,
    BackupDownloadParams,
    BackupsInfo,
    BackupUploadParams,
    BackupInfoParams,
)


class BackupRepository(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def upload(self, request: BackupUploadParams) -> BackupPieces:
        raise NotImplementedError

    @abc.abstractmethod
    def download(self, request: BackupDownloadParams) -> BackupPieces:
        raise NotImplementedError

    @abc.abstractmethod
    def get_info(self, request: BackupInfoParams) -> BackupsInfo:
        raise NotImplementedError
