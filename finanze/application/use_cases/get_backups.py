import logging
from datetime import datetime, timedelta
from typing import Optional

from dateutil.tz import tzlocal

from application.ports.backup_local_registry import BackupLocalRegistry
from application.ports.backup_repository import BackupRepository
from application.ports.cloud_register import CloudRegister
from application.ports.datasource_backup_port import Backupable
from domain.backup import (
    FullBackupInfo,
    FullBackupsInfo,
    SyncStatus,
    BackupInfo,
    BackupFileType,
    BackupsInfoRequest,
    BackupsInfo,
    BackupInfoParams,
)
from domain.cloud_auth import (
    CloudAuthData,
    CloudAuthToken,
    CloudPermission,
    CloudUserRole,
)
from domain.exception.exceptions import TooManyRequests
from domain.use_cases.get_backups import GetBackups


class GetBackupsImpl(GetBackups):
    GET_INFO_COOLDOWN_MINUTES = {
        CloudUserRole.PLUS: 0,
        CloudUserRole.BASIC: 60,
    }

    def __init__(
        self,
        backupable_ports: dict[BackupFileType, Backupable],
        backup_repository: BackupRepository,
        backup_local_registry: BackupLocalRegistry,
        cloud_register: CloudRegister,
    ):
        self._backupable_ports = backupable_ports
        self._backup_repository = backup_repository
        self._backup_local_registry = backup_local_registry
        self._cloud_register = cloud_register
        self._last_remote_fetch: datetime | None = None

        self._log = logging.getLogger(__name__)

    async def execute(
        self,
        request: BackupsInfoRequest,
        cloud_token: Optional[CloudAuthToken] = None,
    ) -> FullBackupsInfo:
        if cloud_token:
            token_data = await self._cloud_register.decode_token(
                cloud_token.access_token
            )
            user_auth = CloudAuthData(
                role=token_data.role,
                permissions=token_data.permissions,
                token=cloud_token,
                email=token_data.email,
            )
        else:
            user_auth = await self._cloud_register.get_auth()
        CloudPermission.BACKUP_INFO.check(user_auth)

        if cloud_token:
            local_bkg_info = BackupsInfo(pieces={})
        else:
            local_bkg_info = await self._backup_local_registry.get_info()
        remote_bkg_info = BackupsInfo(pieces={})
        if not request.only_local:
            if not cloud_token:
                self._check_info_cooldown(user_auth.role)
            remote_bkg_info = await self._backup_repository.get_info(
                BackupInfoParams(auth=user_auth)
            )
            if not cloud_token:
                self._last_remote_fetch = datetime.now(tzlocal())

        full_backup_pieces = {}

        for backup_type in BackupFileType:
            backupable = self._backupable_ports.get(backup_type)
            if backupable is None:
                continue

            if cloud_token:
                remote_backup = remote_bkg_info.pieces.get(backup_type)
                if remote_backup is None:
                    continue
                full_backup_pieces[backup_type] = FullBackupInfo(
                    local=None,
                    remote=remote_backup,
                    last_update=remote_backup.date,
                    has_local_changes=False,
                    status=None,
                )
                continue

            last_update = await backupable.get_last_updated()

            local_backup = local_bkg_info.pieces.get(backup_type)
            remote_backup = remote_bkg_info.pieces.get(backup_type)

            status, has_local_changes = self._calculate_sync_status(
                local_backup, remote_backup, last_update
            )

            full_backup_pieces[backup_type] = FullBackupInfo(
                local=local_backup,
                remote=remote_backup if not request.only_local else None,
                last_update=last_update,
                has_local_changes=has_local_changes,
                status=status if not request.only_local else None,
            )

        return FullBackupsInfo(pieces=full_backup_pieces)

    def _check_info_cooldown(self, role: CloudUserRole):
        cooldown_minutes = self.GET_INFO_COOLDOWN_MINUTES.get(role, 0)
        if cooldown_minutes <= 0 or self._last_remote_fetch is None:
            return
        now = datetime.now(tzlocal())
        cooldown_delta = timedelta(minutes=cooldown_minutes)
        elapsed = now - self._last_remote_fetch
        if elapsed < cooldown_delta:
            remaining_seconds = int((cooldown_delta - elapsed).total_seconds())
            self._log.debug(
                "Get info blocked: last remote fetch was %s seconds ago, cooldown is %s minutes",
                int(elapsed.total_seconds()),
                cooldown_minutes,
            )
            raise TooManyRequests(
                f"Please wait {remaining_seconds} seconds before checking backup status"
            )

    @staticmethod
    def _status_for_both_exist(
        local: BackupInfo, remote: BackupInfo, has_local_changes: bool
    ) -> SyncStatus:
        # Same backup on both sides
        if local.id == remote.id:
            return SyncStatus.PENDING if has_local_changes else SyncStatus.SYNC

        # Different backups - need to determine relationship
        if local.date > remote.date:
            # Our backup is newer (remote rolled back somehow - need to re-upload)
            return SyncStatus.PENDING

        if local.date < remote.date:
            # Remote is newer
            return SyncStatus.CONFLICT if has_local_changes else SyncStatus.OUTDATED

        # Same date but different IDs - unusual, treat as conflict
        return SyncStatus.CONFLICT

    @staticmethod
    def _calculate_sync_status(
        local: BackupInfo | None, remote: BackupInfo | None, last_update: datetime
    ) -> tuple[SyncStatus, bool]:
        # Sync Status Decision Table:
        # +---------------+---------------+------------------+----------+-------------------------------------------------------------+
        # | Local Backup  | Remote Backup | has_local_changes| Status   | Description                                                 |
        # +---------------+---------------+------------------+----------+-------------------------------------------------------------+
        # | None          | None          | Yes              | PENDING  | Fresh data, never backed up                                 |
        # | None          | None          | No               | MISSING  | No data and no backups                                      |
        # | Exists        | None          | Yes              | PENDING  | Remote was deleted, has new changes, need to re-upload      |
        # | Exists        | None          | No               | PENDING  | Remote was deleted, need to re-upload                       |
        # | None          | Exists        | Yes              | CONFLICT | Remote exists, we have local changes but no local backup    |
        # | None          | Exists        | No               | OUTDATED | Remote exists, we need to download it                       |
        # | Same ID       | Same ID       | Yes              | PENDING  | Synced but has new local changes                            |
        # | Same ID       | Same ID       | No               | SYNC     | Fully synchronized                                          |
        # | Local newer   | Remote older  | Yes              | PENDING  | Remote rolled back somehow, has new changes, need to upload |
        # | Local newer   | Remote older  | No               | PENDING  | Remote rolled back somehow, need to re-upload               |
        # | Local older   | Remote newer  | Yes              | CONFLICT | Remote updated AND we have local changes                    |
        # | Local older   | Remote newer  | No               | OUTDATED | Remote updated, we need to download                         |
        # | Same date     | Diff ID       | Any              | CONFLICT | Edge case, treat as conflict                                |
        # +---------------+---------------+------------------+----------+-------------------------------------------------------------+

        has_local_changes = local is None or last_update > local.date

        # No backups exist at all
        if local is None and remote is None:
            return (
                SyncStatus.PENDING if has_local_changes else SyncStatus.MISSING
            ), has_local_changes

        # Only local backup exists (remote was deleted - need to re-upload)
        if remote is None:
            return SyncStatus.PENDING, has_local_changes

        # Only remote backup exists
        if local is None:
            return (
                SyncStatus.CONFLICT if has_local_changes else SyncStatus.OUTDATED
            ), has_local_changes

        # Both local and remote backups exist
        return GetBackupsImpl._status_for_both_exist(
            local, remote, has_local_changes
        ), has_local_changes
