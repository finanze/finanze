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
    async def upload(self, request: BackupUploadParams) -> BackupPieces:
        raise NotImplementedError

    @abc.abstractmethod
    async def download(self, request: BackupDownloadParams) -> BackupPieces:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_info(self, request: BackupInfoParams) -> BackupsInfo:
        raise NotImplementedError
