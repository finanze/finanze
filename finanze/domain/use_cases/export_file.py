import abc

from domain.export import FileExportRequest, FileExportResult


class ExportFile(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: FileExportRequest) -> FileExportResult:
        raise NotImplementedError
