from application.ports.backup_settings_port import BackupSettingsPort
from domain.backup import BackupSettings
from domain.use_cases.save_backup_settings import SaveBackupSettings


class SaveBackupSettingsImpl(SaveBackupSettings):
    def __init__(self, backup_settings_port: BackupSettingsPort):
        self._backup_settings_port = backup_settings_port

    async def execute(self, settings: BackupSettings) -> BackupSettings:
        await self._backup_settings_port.save_backup_settings(settings)
        return settings
