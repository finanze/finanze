import abc

from domain.virtual_fetch_result import VirtualFetchResult


class VirtualFetch(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> VirtualFetchResult:
        raise NotImplementedError
