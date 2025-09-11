import abc

from domain.external_entity import CompleteExternalEntityLinkRequest


class CompleteExternalEntityConnection(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: CompleteExternalEntityLinkRequest):
        raise NotImplementedError
