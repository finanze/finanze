import abc

from domain.backup import BackupSettings


class SaveBackupSettings(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, settings: BackupSettings) -> BackupSettings:
        raise NotImplementedError
