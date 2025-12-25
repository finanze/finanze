import abc

from domain.backup import BackupSettings


class BackupSettingsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_backup_settings(self) -> BackupSettings:
        raise NotImplementedError

    @abc.abstractmethod
    def save_backup_settings(self, settings: BackupSettings):
        raise NotImplementedError
