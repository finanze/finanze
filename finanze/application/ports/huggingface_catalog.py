import abc

from domain.local_model import HuggingFaceQuants


class HuggingFaceCatalog(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def list_quants(self, repo: str) -> HuggingFaceQuants:
        raise NotImplementedError
