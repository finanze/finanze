import abc
from typing import Optional

from domain.file_upload import FileUpload


class FileStoragePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, file: FileUpload, folder: str, keep_name: bool = False) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    async def save_from_url(
        self, file_url: str, folder: str, filename: Optional[str] = None
    ) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, file_path: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def get_url(self, file_path: str) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_by_url(self, file_url: str) -> bool:
        raise NotImplementedError
