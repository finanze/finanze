from abc import ABC, abstractmethod

from domain.backup import BackupFileType


class FileTransferStrategy(ABC):
    @abstractmethod
    async def upload(
        self,
        url: str,
        method: str,
        payload: bytes,
        headers: dict[str, str],
        backup_type: BackupFileType,
    ) -> None:
        pass

    @abstractmethod
    async def download(self, url: str, backup_type: BackupFileType) -> bytes:
        pass
