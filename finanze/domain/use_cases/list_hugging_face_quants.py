import abc

from domain.local_model import HuggingFaceQuants


class ListHuggingFaceQuants(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, repo: str) -> HuggingFaceQuants:
        raise NotImplementedError
