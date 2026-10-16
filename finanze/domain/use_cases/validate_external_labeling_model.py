import abc

from domain.external_labeling import (
    ExternalLabelingModelValidation,
    ValidateExternalLabelingModelRequest,
)


class ValidateExternalLabelingModel(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, request: ValidateExternalLabelingModelRequest
    ) -> ExternalLabelingModelValidation:
        raise NotImplementedError
