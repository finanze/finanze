import abc

from domain.external_labeling import ExternalLabelingModels


class GetExternalLabelingModels(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, provider_id: str) -> ExternalLabelingModels:
        raise NotImplementedError
