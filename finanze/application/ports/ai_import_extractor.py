import abc

from domain.importing import AIImportExtraction, AIImportRequest


class AIImportExtractor(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def extract(self, request: AIImportRequest) -> AIImportExtraction:
        raise NotImplementedError
