import abc

from domain.fetch_result import FetchResult


class VirtualFetch(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> FetchResult:
        raise NotImplementedError
