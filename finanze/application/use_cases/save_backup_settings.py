from application.ports.backup_settings_port import BackupSettingsPort
from application.ports.cloud_register import CloudRegister
from domain.backup import BackupSettings, BackupMode
from domain.cloud_auth import CloudPermission
from domain.use_cases.save_backup_settings import SaveBackupSettings


class SaveBackupSettingsImpl(SaveBackupSettings):
    def __init__(
        self,
        backup_settings_port: BackupSettingsPort,
        cloud_register: CloudRegister,
    ):
        self._backup_settings_port = backup_settings_port
        self._cloud_register = cloud_register

    async def execute(self, settings: BackupSettings) -> BackupSettings:
        if settings.mode == BackupMode.AUTO:
            user_auth = await self._cloud_register.get_auth()
            CloudPermission.BACKUP_AUTO.check(user_auth)
        await self._backup_settings_port.save_backup_settings(settings)
        return settings
