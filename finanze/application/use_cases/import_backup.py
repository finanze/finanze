import logging
from datetime import datetime, timedelta

from dateutil.tz import tzlocal

from application.ports.backup_local_registry import BackupLocalRegistry
from application.ports.backup_processor import BackupProcessor
from application.ports.backup_repository import BackupRepository
from application.ports.cloud_register import CloudRegister
from application.ports.datasource_backup_port import Backupable
from application.ports.datasource_initiator import DatasourceInitiator
from domain.backup import (
    BackupProcessRequest,
    ImportBackupRequest,
    BackupFileType,
    BackupDownloadParams,
    BackupInfo,
    BackupSyncResult,
    FullBackupInfo,
    SyncStatus,
    BackupInfoParams,
)
from domain.cloud_auth import CloudPermission
from domain.exception.exceptions import (
    InvalidBackupCredentials,
    TooManyRequests,
    BackupConflict,
)
from domain.use_cases.import_backup import ImportBackup


class ImportBackupImpl(ImportBackup):
    BACKUP_OPERATION_COOLDOWN_MINUTES = 5

    def __init__(
        self,
        data_initiator: DatasourceInitiator,
        backupable_ports: dict[BackupFileType, Backupable],
        backup_processor: BackupProcessor,
        backup_repository: BackupRepository,
        backup_local_registry: BackupLocalRegistry,
        cloud_register: CloudRegister,
    ):
        self._data_initiator = data_initiator
        self._backupable_ports = backupable_ports
        self._backup_processor = backup_processor
        self._backup_repository = backup_repository
        self._backup_local_registry = backup_local_registry
        self._cloud_register = cloud_register

        self._log = logging.getLogger(__name__)

    async def execute(self, request: ImportBackupRequest) -> BackupSyncResult:
        user_auth = await self._cloud_register.get_auth()
        CloudPermission.BACKUP_IMPORT.check(user_auth)

        await self._check_cooldown()

        bkg_pass = request.password or await self._data_initiator.get_hashed_password()
        if bkg_pass is None:
            raise InvalidBackupCredentials("NO_PASSWORD_PROVIDED")

        remote_backup_pieces = (
            await self._backup_repository.get_info(BackupInfoParams(auth=user_auth))
        ).pieces
        local_backup_registry = (await self._backup_local_registry.get_info()).pieces
        self._log.debug("Found %d backup pieces", len(remote_backup_pieces))

        piece_types_to_import = set()
        for piece in remote_backup_pieces.values():
            if piece.type not in request.types:
                continue

            backupable = self._backupable_ports.get(piece.type)
            if backupable is None:
                self._log.warning(
                    "No backupable port found for backup piece type %s, skipping import",
                    piece.type,
                )
                continue

            local_backup = local_backup_registry.get(piece.type)
            local_last_update = await backupable.get_last_updated()
            has_local_changes = (
                local_backup is None or local_last_update > local_backup.date
            )

            # Already synced with this exact backup
            if local_backup is not None and piece.id == local_backup.id:
                if has_local_changes:
                    self._log.debug(
                        "Skipping import of %s backup piece %s: already imported, but has pending local changes",
                        piece.type,
                        piece.id,
                    )
                else:
                    self._log.debug(
                        "Skipping import of %s backup piece %s: already imported and in sync",
                        piece.type,
                        piece.id,
                    )
                continue

            # Remote is same age or older than our local backup - nothing new to import
            if local_backup is not None and piece.date <= local_backup.date:
                self._log.debug(
                    "Skipping import of %s backup piece %s: our local backup is newer or equal",
                    piece.type,
                    piece.id,
                )
                continue

            # CONFLICT: Remote is newer, but we have local uncommitted changes
            if has_local_changes and not request.force:
                self._log.warning(
                    "Conflict detected for %s: remote backup is newer but local has uncommitted changes",
                    piece.type,
                )
                raise BackupConflict(
                    f"Conflict detected for {piece.type.value}: remote backup is newer but you have local changes. "
                    "Upload your changes first or use force import to overwrite local data."
                )

            piece_types_to_import.add(piece.type)

        pieces = await self._backup_repository.download(
            BackupDownloadParams(types=list(piece_types_to_import), auth=user_auth)
        )

        imported_backup_infos = []
        affected_pieces = {}
        for piece in pieces.pieces:
            backupable = self._backupable_ports.get(piece.type)

            process_request = BackupProcessRequest(
                protocol=piece.protocol,
                password=bkg_pass,
                type=piece.type,
                payload=piece.payload,
            )
            downloaded_data = await self._backup_processor.decompile(process_request)
            await backupable.import_data(downloaded_data.payload)

            # Register the imported backup locally so we know we're in sync
            backup_info = BackupInfo(
                id=piece.id,
                protocol=piece.protocol,
                date=piece.date,
                type=piece.type,
                size=piece.size,
            )
            imported_backup_infos.append(backup_info)

            # Get updated state after import
            affected_pieces[piece.type] = FullBackupInfo(
                local=backup_info,
                remote=backup_info,
                last_update=piece.date,
                has_local_changes=False,
                status=SyncStatus.SYNC,
            )

        if imported_backup_infos:
            await self._backup_local_registry.insert(imported_backup_infos)

        return BackupSyncResult(pieces=affected_pieces)

    async def _check_cooldown(self):
        local_backup_registry = (await self._backup_local_registry.get_info()).pieces
        if not local_backup_registry:
            return

        now = datetime.now(tzlocal())
        cooldown_delta = timedelta(minutes=self.BACKUP_OPERATION_COOLDOWN_MINUTES)

        for backup_info in local_backup_registry.values():
            time_since_last_operation = now - backup_info.date
            if time_since_last_operation < cooldown_delta:
                remaining_seconds = int(
                    (cooldown_delta - time_since_last_operation).total_seconds()
                )
                self._log.warning(
                    "Import operation blocked: last backup was %s seconds ago, cooldown is %s minutes",
                    int(time_since_last_operation.total_seconds()),
                    self.BACKUP_OPERATION_COOLDOWN_MINUTES,
                )
                raise TooManyRequests(
                    f"Please wait {remaining_seconds} seconds before performing another backup operation"
                )
