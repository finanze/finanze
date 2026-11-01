import abc

from domain.local_model import ImportedLocalModel, ImportLocalModelRequest


class ImportLocalModel(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: ImportLocalModelRequest) -> ImportedLocalModel:
        raise NotImplementedError
