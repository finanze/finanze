import abc

from domain.importing import ImportResult


class ImportSheets(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> ImportResult:
        raise NotImplementedError
