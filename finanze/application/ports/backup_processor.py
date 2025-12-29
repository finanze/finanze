import abc

from domain.backup import BackupProcessRequest, BackupProcessResult


class BackupProcessor(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def decompile(self, data: BackupProcessRequest) -> BackupProcessResult:
        raise NotImplementedError

    @abc.abstractmethod
    def compile(self, data: BackupProcessRequest) -> BackupProcessResult:
        raise NotImplementedError
