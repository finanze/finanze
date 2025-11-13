import abc

from domain.import_result import ImportResult


class ImportSheets(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> ImportResult:
        raise NotImplementedError
