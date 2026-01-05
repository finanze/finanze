import abc

from domain.backup import BackupSettings


class BackupSettingsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_backup_settings(self) -> BackupSettings:
        raise NotImplementedError

    @abc.abstractmethod
    async def save_backup_settings(self, settings: BackupSettings):
        raise NotImplementedError
