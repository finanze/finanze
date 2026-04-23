import abc

from domain.backup import BackupProcessRequest, BackupProcessResult


class BackupProcessor(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def decompile(self, data: BackupProcessRequest) -> BackupProcessResult:
        raise NotImplementedError

    @abc.abstractmethod
    async def compile(self, data: BackupProcessRequest) -> BackupProcessResult:
        raise NotImplementedError
