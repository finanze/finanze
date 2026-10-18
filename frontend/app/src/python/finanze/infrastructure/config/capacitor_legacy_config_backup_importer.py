from domain.backup import BackupFileType
from infrastructure.cloud.backup.capacitor_backup_processor import (
    delete_staging_file,
    read_staging_file,
)
from infrastructure.cloud.backup.staging_registry import get_file_name
from infrastructure.config.legacy_config_backup_importer import (
    LegacyConfigBackupImporter,
)


class CapacitorLegacyConfigBackupImporter(LegacyConfigBackupImporter):
    async def import_data(self, data: bytes):
        file_name = get_file_name(BackupFileType.CONFIG, "decompiled")
        try:
            raw = await read_staging_file(file_name)
        finally:
            await delete_staging_file(file_name)
        await super().import_data(raw)
