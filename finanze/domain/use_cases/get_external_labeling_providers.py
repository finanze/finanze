import abc

from domain.external_labeling import ExternalLabelingProviders


class GetExternalLabelingProviders(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> ExternalLabelingProviders:
        raise NotImplementedError
