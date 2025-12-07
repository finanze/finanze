import abc

from domain.importing import ImportFileRequest, ImportResult


class ImportFile(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: ImportFileRequest) -> ImportResult:
        raise NotImplementedError
