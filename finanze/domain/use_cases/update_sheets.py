import abc

from domain.export import ExportRequest


class UpdateSheets(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def execute(self, request: ExportRequest):
        raise NotImplementedError
