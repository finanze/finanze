from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.use_cases.upload_backup import UploadBackupImpl
from domain.backup import (
    BackupFileType,
    BackupInfo,
    BackupPieces,
    BackupProcessResult,
    BackupTransferPiece,
    BackupsInfo,
    SyncStatus,
    UploadBackupRequest,
)
from domain.cloud_auth import (
    CloudAuthData,
    CloudAuthToken,
    CloudUserRole,
)
from domain.exception.exceptions import (
    BackupConflict,
    PermissionDenied,
    TooManyRequests,
)

NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=tzlocal())
EARLIER = NOW - timedelta(hours=1)
LATER = NOW + timedelta(hours=1)
LONG_AGO = NOW - timedelta(hours=24)


def _make_auth(permissions=None):
    return CloudAuthData(
        role=CloudUserRole.PLUS,
        permissions=permissions or ["backup.create"],
        token=CloudAuthToken(
            access_token="access",
            refresh_token="refresh",
            token_type="bearer",
            expires_at=9999999999,
        ),
        email="test@test.com",
    )


def _make_backup_info(
    backup_type=BackupFileType.DATA, date=None, backup_id=None, size=100
):
    return BackupInfo(
        id=backup_id or uuid4(),
        protocol=1,
        date=date or NOW,
        type=backup_type,
        size=size,
    )


def _make_transfer_piece(
    backup_type=BackupFileType.DATA, date=None, piece_id=None, size=100
):
    return BackupTransferPiece(
        id=piece_id or uuid4(),
        protocol=1,
        date=date or NOW,
        type=backup_type,
        payload=b"encrypted_data",
        size=size,
    )


def _build_use_case(
    auth=None,
    local_info=None,
    remote_info=None,
    upload_result=None,
    backupable_ports=None,
    hashed_password="hashed_pass",
    compile_result=None,
):
    cloud_register = MagicMock()
    cloud_register.get_auth = AsyncMock(return_value=auth or _make_auth())

    local_registry = MagicMock()
    local_registry.get_info = AsyncMock(
        return_value=local_info or BackupsInfo(pieces={})
    )
    local_registry.insert = AsyncMock()

    backup_repo = MagicMock()
    backup_repo.get_info = AsyncMock(return_value=remote_info or BackupsInfo(pieces={}))
    backup_repo.upload = AsyncMock(
        return_value=upload_result or BackupPieces(pieces=[])
    )

    data_initiator = MagicMock()
    data_initiator.get_hashed_password = AsyncMock(return_value=hashed_password)

    processor = MagicMock()
    processor.compile = AsyncMock(
        return_value=compile_result or BackupProcessResult(payload=b"compiled", size=50)
    )
    processor.decompile = AsyncMock(
        return_value=BackupProcessResult(payload=b"decompiled", size=50)
    )

    if backupable_ports is None:
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)
        backupable.export = AsyncMock(return_value=b"data")
        backupable.import_data = AsyncMock()
        backupable_ports = {BackupFileType.DATA: backupable}

    use_case = UploadBackupImpl(
        data_initiator=data_initiator,
        backupable_ports=backupable_ports,
        backup_processor=processor,
        backup_repository=backup_repo,
        backup_local_registry=local_registry,
        cloud_register=cloud_register,
    )
    return (
        use_case,
        cloud_register,
        local_registry,
        backup_repo,
        processor,
        data_initiator,
        backupable_ports,
    )


class TestUploadPermissions:
    @pytest.mark.asyncio
    async def test_raises_permission_denied(self):
        auth = _make_auth(permissions=["other.permission"])
        use_case, *_ = _build_use_case(auth=auth)

        with pytest.raises(PermissionDenied):
            await use_case.execute(UploadBackupRequest(types=[BackupFileType.DATA]))


class TestUploadCooldown:
    @pytest.mark.asyncio
    async def test_raises_too_many_requests_during_cooldown(self):
        recent_date = datetime.now(tzlocal()) - timedelta(minutes=1)
        local_info = BackupsInfo(
            pieces={
                BackupFileType.DATA: _make_backup_info(date=recent_date),
            }
        )
        use_case, *_ = _build_use_case(local_info=local_info)

        with pytest.raises(TooManyRequests):
            await use_case.execute(UploadBackupRequest(types=[BackupFileType.DATA]))


class TestUploadSkips:
    @pytest.mark.asyncio
    async def test_skips_when_no_local_changes_and_remote_exists(self):
        shared_id = uuid4()
        local_backup = _make_backup_info(date=LONG_AGO, backup_id=shared_id)
        remote_backup = _make_backup_info(date=LONG_AGO, backup_id=shared_id)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=LONG_AGO)
        backupable.export = AsyncMock(return_value=b"data")
        backupable.import_data = AsyncMock()

        use_case, _, local_registry, backup_repo, processor, _, _ = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            backupable_ports={BackupFileType.DATA: backupable},
        )

        result = await use_case.execute(
            UploadBackupRequest(types=[BackupFileType.DATA])
        )

        assert result.pieces == {}
        assert backupable.export.call_count == 0
        assert local_registry.insert.call_count == 0


class TestUploadConflict:
    @pytest.mark.asyncio
    async def test_raises_conflict_when_remote_changed_since_last_sync(self):
        local_backup = _make_backup_info(date=EARLIER)
        remote_backup = _make_backup_info(date=LATER)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)
        backupable.export = AsyncMock(return_value=b"data")
        backupable.import_data = AsyncMock()

        use_case, *_ = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            backupable_ports={BackupFileType.DATA: backupable},
        )

        with pytest.raises(BackupConflict):
            await use_case.execute(UploadBackupRequest(types=[BackupFileType.DATA]))

    @pytest.mark.asyncio
    async def test_raises_conflict_when_no_local_backup_and_remote_exists(self):
        remote_backup = _make_backup_info(date=NOW)
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)
        backupable.export = AsyncMock(return_value=b"data")
        backupable.import_data = AsyncMock()

        use_case, *_ = _build_use_case(
            remote_info=remote_info,
            backupable_ports={BackupFileType.DATA: backupable},
        )

        with pytest.raises(BackupConflict):
            await use_case.execute(UploadBackupRequest(types=[BackupFileType.DATA]))


class TestUploadForce:
    @pytest.mark.asyncio
    async def test_uploads_with_force_despite_conflict(self):
        local_backup = _make_backup_info(date=EARLIER)
        remote_backup = _make_backup_info(date=LATER)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)
        backupable.export = AsyncMock(return_value=b"data")
        backupable.import_data = AsyncMock()

        uploaded_piece = _make_transfer_piece(date=NOW)
        upload_result = BackupPieces(pieces=[uploaded_piece])

        use_case, _, local_registry, backup_repo, processor, _, _ = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            backupable_ports={BackupFileType.DATA: backupable},
            upload_result=upload_result,
        )

        result = await use_case.execute(
            UploadBackupRequest(types=[BackupFileType.DATA], force=True)
        )

        assert BackupFileType.DATA in result.pieces
        assert result.pieces[BackupFileType.DATA].status == SyncStatus.SYNC
        assert backup_repo.upload.call_count == 1
        assert processor.compile.call_count == 1


class TestUploadSuccess:
    @pytest.mark.asyncio
    async def test_uploads_and_registers_backup(self):
        piece_id = uuid4()
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)
        backupable.export = AsyncMock(return_value=b"data")
        backupable.import_data = AsyncMock()
        uploaded_piece = _make_transfer_piece(date=NOW, piece_id=piece_id)
        upload_result = BackupPieces(pieces=[uploaded_piece])

        use_case, _, local_registry, backup_repo, processor, _, _ = _build_use_case(
            backupable_ports={BackupFileType.DATA: backupable},
            upload_result=upload_result,
        )

        result = await use_case.execute(
            UploadBackupRequest(types=[BackupFileType.DATA])
        )

        assert BackupFileType.DATA in result.pieces
        assert result.pieces[BackupFileType.DATA].status == SyncStatus.SYNC
        assert result.pieces[BackupFileType.DATA].has_local_changes is False

        assert local_registry.insert.call_count == 1
        inserted = local_registry.insert.call_args[0][0]
        assert len(inserted) == 1
        assert inserted[0].id == piece_id

        assert backup_repo.upload.call_count == 1
        assert processor.compile.call_count == 1
        assert backupable.export.call_count == 1

    @pytest.mark.asyncio
    async def test_no_insert_when_nothing_uploaded(self):
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=LONG_AGO)
        backupable.export = AsyncMock(return_value=b"data")
        backupable.import_data = AsyncMock()
        local_backup = _make_backup_info(date=LONG_AGO)
        remote_backup = _make_backup_info(date=LONG_AGO)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})

        use_case, _, local_registry, *_ = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            backupable_ports={BackupFileType.DATA: backupable},
        )

        result = await use_case.execute(
            UploadBackupRequest(types=[BackupFileType.DATA])
        )

        assert result.pieces == {}
        assert local_registry.insert.call_count == 0

    @pytest.mark.asyncio
    async def test_skips_type_without_backupable_port(self):
        uploaded_piece = _make_transfer_piece(date=NOW)
        upload_result = BackupPieces(pieces=[uploaded_piece])
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)
        backupable.export = AsyncMock(return_value=b"data")
        backupable.import_data = AsyncMock()

        use_case, _, local_registry, backup_repo, *_ = _build_use_case(
            backupable_ports={BackupFileType.DATA: backupable},
            upload_result=upload_result,
        )

        result = await use_case.execute(
            UploadBackupRequest(types=[BackupFileType.CONFIG])
        )

        assert BackupFileType.CONFIG not in result.pieces
