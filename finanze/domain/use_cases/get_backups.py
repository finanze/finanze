import abc

from domain.backup import FullBackupsInfo, BackupsInfoRequest


class GetBackups(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: BackupsInfoRequest) -> FullBackupsInfo:
        raise NotImplementedError
