import abc

from domain.file_upload import FileUpload


class FileStoragePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, file: FileUpload, folder: str) -> str:
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
