import abc

from domain.export import FileFormat
from domain.file_upload import FileUpload


class TableRWPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def convert(self, rows: list[list[str]], format: FileFormat) -> bytes:
        raise NotImplementedError

    @abc.abstractmethod
    def parse(self, upload: FileUpload) -> list[list[str]]:
        raise NotImplementedError
