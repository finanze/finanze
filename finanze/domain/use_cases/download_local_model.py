import abc

from domain.local_model import DownloadLocalModelRequest


class DownloadLocalModel(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: DownloadLocalModelRequest):
        raise NotImplementedError
