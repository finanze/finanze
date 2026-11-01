import abc

from domain.ai import AIModelValidation, ValidateAIModelRequest


class ValidateAIModel(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: ValidateAIModelRequest) -> AIModelValidation:
        raise NotImplementedError
