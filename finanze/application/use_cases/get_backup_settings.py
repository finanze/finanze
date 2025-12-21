from application.ports.backup_settings_port import BackupSettingsPort
from domain.backup import BackupSettings
from domain.use_cases.get_backup_settings import GetBackupSettings


class GetBackupSettingsImpl(GetBackupSettings):
    def __init__(self, backup_settings_port: BackupSettingsPort):
        self._backup_settings_port = backup_settings_port

    def execute(self) -> BackupSettings:
        return self._backup_settings_port.get_backup_settings()
