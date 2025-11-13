import abc

from domain.export import ExportRequest


class ExportSheets(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: ExportRequest):
        raise NotImplementedError
