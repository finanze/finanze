from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.use_cases.import_backup import ImportBackupImpl
from domain.backup import (
    BackupFileType,
    BackupInfo,
    BackupPieces,
    BackupProcessResult,
    BackupTransferPiece,
    BackupsInfo,
    ImportBackupRequest,
    SyncStatus,
)
from domain.cloud_auth import (
    CloudAuthData,
    CloudAuthToken,
    CloudUserRole,
)
from domain.exception.exceptions import (
    BackupConflict,
    InvalidBackupCredentials,
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
        permissions=permissions or ["backup.import"],
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
    download_result=None,
    backupable_ports=None,
    hashed_password="hashed_pass",
    decompile_result=None,
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
    backup_repo.download = AsyncMock(
        return_value=download_result or BackupPieces(pieces=[])
    )

    data_initiator = MagicMock()
    data_initiator.get_hashed_password = AsyncMock(return_value=hashed_password)

    processor = MagicMock()
    processor.decompile = AsyncMock(
        return_value=decompile_result
        or BackupProcessResult(payload=b"decompiled", size=50)
    )
    processor.compile = AsyncMock(
        return_value=BackupProcessResult(payload=b"compiled", size=50)
    )

    if backupable_ports is None:
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)
        backupable.export = AsyncMock(return_value=b"data")
        backupable.import_data = AsyncMock()
        backupable_ports = {BackupFileType.DATA: backupable}

    use_case = ImportBackupImpl(
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


class TestImportPermissions:
    @pytest.mark.asyncio
    async def test_raises_permission_denied(self):
        auth = _make_auth(permissions=["other.permission"])
        use_case, *_ = _build_use_case(auth=auth)

        with pytest.raises(PermissionDenied):
            await use_case.execute(
                ImportBackupRequest(types=[BackupFileType.DATA], password="pass")
            )


class TestImportCooldown:
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
            await use_case.execute(
                ImportBackupRequest(types=[BackupFileType.DATA], password="pass")
            )

    @pytest.mark.asyncio
    async def test_no_cooldown_when_old_backup(self):
        old_date = datetime.now(tzlocal()) - timedelta(minutes=10)
        piece_id = uuid4()
        remote_backup = _make_backup_info(date=LATER, backup_id=piece_id)
        local_info = BackupsInfo(
            pieces={
                BackupFileType.DATA: _make_backup_info(date=old_date),
            }
        )
        remote_info = BackupsInfo(
            pieces={
                BackupFileType.DATA: remote_backup,
            }
        )
        transfer_piece = _make_transfer_piece(date=LATER, piece_id=piece_id)
        download_result = BackupPieces(pieces=[transfer_piece])
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=old_date)
        backupable.import_data = AsyncMock()
        backupable.export = AsyncMock(return_value=b"data")
        use_case, *_ = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            download_result=download_result,
            backupable_ports={BackupFileType.DATA: backupable},
        )

        result = await use_case.execute(
            ImportBackupRequest(types=[BackupFileType.DATA], password="pass")
        )
        assert BackupFileType.DATA in result.pieces


class TestImportCredentials:
    @pytest.mark.asyncio
    async def test_raises_invalid_credentials_when_no_password(self):
        use_case, *_ = _build_use_case(hashed_password=None)

        with pytest.raises(InvalidBackupCredentials):
            await use_case.execute(
                ImportBackupRequest(types=[BackupFileType.DATA], password=None)
            )


class TestImportSkips:
    @pytest.mark.asyncio
    async def test_skips_already_synced_pieces_same_id(self):
        shared_id = uuid4()
        local_backup = _make_backup_info(date=LONG_AGO, backup_id=shared_id)
        remote_backup = _make_backup_info(date=LONG_AGO, backup_id=shared_id)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=LONG_AGO)
        backupable.import_data = AsyncMock()
        backupable.export = AsyncMock(return_value=b"data")

        use_case, _, local_registry, backup_repo, *_ = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            backupable_ports={BackupFileType.DATA: backupable},
        )

        result = await use_case.execute(
            ImportBackupRequest(types=[BackupFileType.DATA], password="pass")
        )

        assert result.pieces == {}
        assert local_registry.insert.call_count == 0

    @pytest.mark.asyncio
    async def test_skips_older_remote_pieces(self):
        local_backup = _make_backup_info(date=LATER)
        remote_backup = _make_backup_info(date=EARLIER)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=LONG_AGO)
        backupable.import_data = AsyncMock()
        backupable.export = AsyncMock(return_value=b"data")

        use_case, _, local_registry, *_ = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            backupable_ports={BackupFileType.DATA: backupable},
        )

        result = await use_case.execute(
            ImportBackupRequest(types=[BackupFileType.DATA], password="pass")
        )

        assert result.pieces == {}
        assert local_registry.insert.call_count == 0

    @pytest.mark.asyncio
    async def test_skips_equal_date_remote_pieces(self):
        local_backup = _make_backup_info(date=NOW)
        remote_backup = _make_backup_info(date=NOW)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=LONG_AGO)
        backupable.import_data = AsyncMock()
        backupable.export = AsyncMock(return_value=b"data")

        use_case, _, local_registry, *_ = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            backupable_ports={BackupFileType.DATA: backupable},
        )

        result = await use_case.execute(
            ImportBackupRequest(types=[BackupFileType.DATA], password="pass")
        )

        assert result.pieces == {}


class TestImportConflict:
    @pytest.mark.asyncio
    async def test_raises_conflict_when_local_changes_not_forced(self):
        local_backup = _make_backup_info(date=EARLIER)
        remote_backup = _make_backup_info(date=LATER)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)
        backupable.import_data = AsyncMock()
        backupable.export = AsyncMock(return_value=b"data")

        use_case, *_ = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            backupable_ports={BackupFileType.DATA: backupable},
        )

        with pytest.raises(BackupConflict):
            await use_case.execute(
                ImportBackupRequest(types=[BackupFileType.DATA], password="pass")
            )


class TestImportForce:
    @pytest.mark.asyncio
    async def test_imports_when_forced_despite_local_changes(self):
        piece_id = uuid4()
        local_backup = _make_backup_info(date=EARLIER)
        remote_backup = _make_backup_info(date=LATER, backup_id=piece_id)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        transfer_piece = _make_transfer_piece(date=LATER, piece_id=piece_id)
        download_result = BackupPieces(pieces=[transfer_piece])
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)
        backupable.import_data = AsyncMock()
        backupable.export = AsyncMock(return_value=b"data")

        use_case, _, local_registry, backup_repo, processor, _, ports = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            download_result=download_result,
            backupable_ports={BackupFileType.DATA: backupable},
        )

        result = await use_case.execute(
            ImportBackupRequest(
                types=[BackupFileType.DATA], password="pass", force=True
            )
        )

        assert BackupFileType.DATA in result.pieces
        assert result.pieces[BackupFileType.DATA].status == SyncStatus.SYNC
        assert processor.decompile.call_count == 1
        assert backupable.import_data.call_count == 1
        assert local_registry.insert.call_count == 1


class TestImportSuccess:
    @pytest.mark.asyncio
    async def test_imports_and_registers_backup(self):
        piece_id = uuid4()
        local_backup = _make_backup_info(date=EARLIER)
        remote_backup = _make_backup_info(date=NOW, backup_id=piece_id)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        transfer_piece = _make_transfer_piece(date=NOW, piece_id=piece_id)
        download_result = BackupPieces(pieces=[transfer_piece])
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=LONG_AGO)
        backupable.import_data = AsyncMock()
        backupable.export = AsyncMock(return_value=b"data")

        use_case, _, local_registry, backup_repo, processor, _, ports = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            download_result=download_result,
            backupable_ports={BackupFileType.DATA: backupable},
        )

        result = await use_case.execute(
            ImportBackupRequest(types=[BackupFileType.DATA], password="pass")
        )

        assert BackupFileType.DATA in result.pieces
        assert result.pieces[BackupFileType.DATA].status == SyncStatus.SYNC
        assert result.pieces[BackupFileType.DATA].has_local_changes is False

        assert local_registry.insert.call_count == 1
        inserted = local_registry.insert.call_args[0][0]
        assert len(inserted) == 1
        assert inserted[0].id == piece_id

        assert processor.decompile.call_count == 1
        assert backupable.import_data.call_count == 1
        assert backupable.import_data.call_args[0][0] == b"decompiled"

    @pytest.mark.asyncio
    async def test_uses_request_password_over_hashed(self):
        piece_id = uuid4()
        local_backup = _make_backup_info(date=EARLIER)
        remote_backup = _make_backup_info(date=NOW, backup_id=piece_id)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        transfer_piece = _make_transfer_piece(date=NOW, piece_id=piece_id)
        download_result = BackupPieces(pieces=[transfer_piece])
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=LONG_AGO)
        backupable.import_data = AsyncMock()
        backupable.export = AsyncMock(return_value=b"data")

        use_case, _, _, _, processor, _, _ = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            download_result=download_result,
            backupable_ports={BackupFileType.DATA: backupable},
            hashed_password="fallback_hash",
        )

        await use_case.execute(
            ImportBackupRequest(types=[BackupFileType.DATA], password="explicit_pass")
        )

        assert processor.decompile.call_args[0][0].password == "explicit_pass"

    @pytest.mark.asyncio
    async def test_falls_back_to_hashed_password(self):
        piece_id = uuid4()
        local_backup = _make_backup_info(date=EARLIER)
        remote_backup = _make_backup_info(date=NOW, backup_id=piece_id)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        transfer_piece = _make_transfer_piece(date=NOW, piece_id=piece_id)
        download_result = BackupPieces(pieces=[transfer_piece])
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=LONG_AGO)
        backupable.import_data = AsyncMock()
        backupable.export = AsyncMock(return_value=b"data")

        use_case, _, _, _, processor, _, _ = _build_use_case(
            local_info=local_info,
            remote_info=remote_info,
            download_result=download_result,
            backupable_ports={BackupFileType.DATA: backupable},
            hashed_password="fallback_hash",
        )

        await use_case.execute(
            ImportBackupRequest(types=[BackupFileType.DATA], password=None)
        )

        assert processor.decompile.call_args[0][0].password == "fallback_hash"

    @pytest.mark.asyncio
    async def test_no_insert_when_nothing_imported(self):
        remote_info = BackupsInfo(pieces={})

        use_case, _, local_registry, *_ = _build_use_case(remote_info=remote_info)

        result = await use_case.execute(
            ImportBackupRequest(types=[BackupFileType.DATA], password="pass")
        )

        assert result.pieces == {}
        assert local_registry.insert.call_count == 0
