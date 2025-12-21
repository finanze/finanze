import logging
from datetime import datetime, timedelta
from uuid import uuid4

from dateutil.tz import tzlocal

from application.ports.backup_local_registry import BackupLocalRegistry
from application.ports.backup_processor import BackupProcessor
from application.ports.backup_repository import BackupRepository
from application.ports.cloud_register import CloudRegister
from application.ports.datasource_backup_port import Backupable
from application.ports.datasource_initiator import DatasourceInitiator
from domain.backup import (
    BackupFileType,
    BackupProcessRequest,
    BackupPieces,
    CURRENT_PROTOCOL_VERSION,
    UploadBackupRequest,
    BackupTransferPiece,
    BackupInfo,
    BackupSyncResult,
    FullBackupInfo,
    SyncStatus,
    BackupUploadParams,
    BackupInfoParams,
)
from domain.cloud_auth import CloudPermission
from domain.exception.exceptions import TooManyRequests, BackupConflict
from domain.use_cases.upload_backup import UploadBackup


class UploadBackupImpl(UploadBackup):
    BACKUP_OPERATION_COOLDOWN_MINUTES = 5
    BACKUP_SIZE_WARNING_THRESHOLD_PERCENT = 5.0

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

    def execute(self, request: UploadBackupRequest) -> BackupSyncResult:
        user_auth = self._cloud_register.get_auth()
        CloudPermission.BACKUP_CREATE.check(user_auth)

        self._check_cooldown()
        hashed_pass = self._data_initiator.get_hashed_password()

        remote_backup_info = self._backup_repository.get_info(
            BackupInfoParams(auth=user_auth)
        ).pieces
        local_backup_registry = self._backup_local_registry.get_info().pieces

        pieces = []
        for bkg_type in request.types:
            piece = self._prepare_piece_for_upload(
                bkg_type,
                hashed_pass,
                local_backup_registry,
                remote_backup_info,
                request.force,
            )
            if piece is not None:
                pieces.append(piece)

        request_pieces = BackupPieces(pieces)
        success_uploads = self._backup_repository.upload(
            BackupUploadParams(pieces=request_pieces, auth=user_auth)
        )

        backup_infos = []
        affected_pieces = {}
        for piece in success_uploads.pieces:
            self._log.debug(
                "Uploaded backup piece: %s (ID: %s, Size: %d bytes)",
                piece.type,
                piece.id,
                len(piece.payload),
            )
            backup_info = BackupInfo(
                id=piece.id,
                protocol=piece.protocol,
                date=piece.date,
                type=piece.type,
                size=len(piece.payload),
            )
            backup_infos.append(backup_info)

            affected_pieces[piece.type] = FullBackupInfo(
                local=backup_info,
                remote=backup_info,
                last_update=piece.date,
                has_local_changes=False,
                status=SyncStatus.SYNC,
            )

        if backup_infos:
            self._backup_local_registry.insert(backup_infos)

        return BackupSyncResult(pieces=affected_pieces)

    def _prepare_piece_for_upload(
        self,
        bkg_type: BackupFileType,
        hashed_pass: str,
        local_backup_registry: dict,
        remote_backup_info: dict,
        force: bool,
    ) -> BackupTransferPiece | None:
        backupable = self._backupable_ports.get(bkg_type)
        if backupable is None:
            return None

        local_last_update = backupable.get_last_updated()
        local_backup = local_backup_registry.get(bkg_type)
        remote_backup = remote_backup_info.get(bkg_type)

        # Check if we have any changes to upload
        has_local_changes = (
            local_backup is None or local_last_update > local_backup.date
        )
        if not has_local_changes and not force:
            self._log.debug(
                "Skipping upload of %s backup piece: no local changes since last backup",
                bkg_type,
            )
            return None

        # CONFLICT: Remote backup changed since our last sync (someone else uploaded)
        self._check_remote_conflict(bkg_type, local_backup, remote_backup, force)

        data = backupable.export()
        local_last_update = backupable.get_last_updated()
        piece = self._handle_bkg(hashed_pass, data, local_last_update, bkg_type)
        if remote_backup:
            local_size = len(piece.payload)
            remote_size = remote_backup.size
            # Calculate size difference percentage (local vs remote)
            if remote_size > 0:
                size_diff_percentage = ((remote_size - local_size) / remote_size) * 100
                # Warn if local backup is BACKUP_SIZE_WARNING_THRESHOLD_PERCENT or smaller than remote
                if size_diff_percentage >= self.BACKUP_SIZE_WARNING_THRESHOLD_PERCENT:
                    self._log.warning(
                        "Uploading %s backup piece with significantly smaller size (%d bytes, %.1f%% smaller) "
                        "than existing remote backup (%d bytes)",
                        bkg_type,
                        local_size,
                        size_diff_percentage,
                        remote_size,
                    )

        return piece

    def _check_remote_conflict(
        self,
        bkg_type: BackupFileType,
        local_backup: BackupInfo | None,
        remote_backup: BackupInfo | None,
        force: bool,
    ):
        if remote_backup is None or force:
            return

        # Check if remote backup is different from what we last synced
        if local_backup is None or remote_backup.id != local_backup.id:
            # Remote changed independently - check if it's newer
            if local_backup is None or remote_backup.date > local_backup.date:
                self._log.warning(
                    "Conflict detected for %s: remote backup changed since our last sync",
                    bkg_type,
                )
                raise BackupConflict(
                    f"Conflict detected for {bkg_type.value}: remote backup has changed since your last sync. "
                    "Import the remote backup first or use force upload to overwrite."
                )

    def _check_cooldown(self):
        local_backup_registry = self._backup_local_registry.get_info().pieces
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
                    "Upload operation blocked: last backup was %s seconds ago, cooldown is %s minutes",
                    int(time_since_last_operation.total_seconds()),
                    self.BACKUP_OPERATION_COOLDOWN_MINUTES,
                )
                raise TooManyRequests(
                    f"Please wait {remaining_seconds} seconds before performing another backup operation"
                )

    def _handle_bkg(
        self,
        password: str,
        data: bytes,
        local_last_update: datetime,
        bkg_type: BackupFileType,
    ) -> BackupTransferPiece:
        data_backup_request = BackupProcessRequest(
            protocol=CURRENT_PROTOCOL_VERSION,
            password=password,
            payload=data,
        )
        compiled = self._backup_processor.compile(data_backup_request)
        return BackupTransferPiece(
            id=uuid4(),
            protocol=CURRENT_PROTOCOL_VERSION,
            date=local_last_update,
            type=bkg_type,
            payload=compiled.payload,
        )
