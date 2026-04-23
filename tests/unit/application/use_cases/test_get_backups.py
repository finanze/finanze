from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.use_cases.get_backups import GetBackupsImpl
from domain.backup import (
    BackupFileType,
    BackupInfo,
    BackupsInfo,
    BackupsInfoRequest,
    SyncStatus,
)
from domain.cloud_auth import (
    CloudAuthData,
    CloudAuthToken,
    CloudUserRole,
)
from domain.exception.exceptions import NoUserLogged, PermissionDenied

NOW = datetime(2025, 6, 1, 12, 0, 0)
EARLIER = NOW - timedelta(hours=1)
LATER = NOW + timedelta(hours=1)


def _make_auth(permissions=None):
    return CloudAuthData(
        role=CloudUserRole.PLUS,
        permissions=permissions or ["backup.info"],
        token=CloudAuthToken(
            access_token="access",
            refresh_token="refresh",
            token_type="bearer",
            expires_at=9999999999,
        ),
        email="test@test.com",
    )


def _make_backup_info(backup_type=BackupFileType.DATA, date=None, backup_id=None):
    return BackupInfo(
        id=backup_id or uuid4(),
        protocol=1,
        date=date or NOW,
        type=backup_type,
        size=100,
    )


class TestCalculateSyncStatus:
    def test_no_local_no_remote_with_local_changes(self):
        status, has_changes = GetBackupsImpl._calculate_sync_status(None, None, NOW)
        assert status == SyncStatus.PENDING
        assert has_changes is True

    def test_no_local_no_remote_no_local_changes(self):
        local = _make_backup_info(date=LATER)
        status, has_changes = GetBackupsImpl._calculate_sync_status(local, None, NOW)
        assert status == SyncStatus.PENDING
        assert has_changes is False

    def test_no_local_no_remote_missing(self):
        status, has_changes = GetBackupsImpl._calculate_sync_status(None, None, NOW)
        assert has_changes is True
        assert status == SyncStatus.PENDING

    def test_only_local_exists_with_changes(self):
        local = _make_backup_info(date=EARLIER)
        status, has_changes = GetBackupsImpl._calculate_sync_status(local, None, NOW)
        assert status == SyncStatus.PENDING
        assert has_changes is True

    def test_only_local_exists_no_changes(self):
        local = _make_backup_info(date=LATER)
        status, has_changes = GetBackupsImpl._calculate_sync_status(local, None, NOW)
        assert status == SyncStatus.PENDING
        assert has_changes is False

    def test_only_remote_exists_with_local_changes(self):
        remote = _make_backup_info(date=NOW)
        status, has_changes = GetBackupsImpl._calculate_sync_status(None, remote, NOW)
        assert status == SyncStatus.CONFLICT
        assert has_changes is True

    def test_only_remote_exists_no_local_changes(self):
        remote = _make_backup_info(date=NOW)
        status, has_changes = GetBackupsImpl._calculate_sync_status(None, remote, NOW)
        assert status == SyncStatus.CONFLICT
        assert has_changes is True

    def test_only_remote_no_local_always_has_changes(self):
        remote = _make_backup_info(date=NOW)
        status, has_changes = GetBackupsImpl._calculate_sync_status(
            None, remote, EARLIER
        )
        assert status == SyncStatus.CONFLICT
        assert has_changes is True

    def test_both_same_id_no_changes(self):
        shared_id = uuid4()
        local = _make_backup_info(date=NOW, backup_id=shared_id)
        remote = _make_backup_info(date=NOW, backup_id=shared_id)
        status, has_changes = GetBackupsImpl._calculate_sync_status(
            local, remote, EARLIER
        )
        assert status == SyncStatus.SYNC
        assert has_changes is False

    def test_both_same_id_with_changes(self):
        shared_id = uuid4()
        local = _make_backup_info(date=NOW, backup_id=shared_id)
        remote = _make_backup_info(date=NOW, backup_id=shared_id)
        status, has_changes = GetBackupsImpl._calculate_sync_status(
            local, remote, LATER
        )
        assert status == SyncStatus.PENDING
        assert has_changes is True

    def test_both_different_id_local_newer(self):
        local = _make_backup_info(date=LATER)
        remote = _make_backup_info(date=NOW)
        status, has_changes = GetBackupsImpl._calculate_sync_status(
            local, remote, EARLIER
        )
        assert status == SyncStatus.PENDING
        assert has_changes is False

    def test_both_different_id_remote_newer_no_changes(self):
        local = _make_backup_info(date=NOW)
        remote = _make_backup_info(date=LATER)
        status, has_changes = GetBackupsImpl._calculate_sync_status(
            local, remote, EARLIER
        )
        assert status == SyncStatus.OUTDATED
        assert has_changes is False

    def test_both_different_id_remote_newer_with_changes(self):
        local = _make_backup_info(date=NOW)
        remote = _make_backup_info(date=LATER)
        status, has_changes = GetBackupsImpl._calculate_sync_status(
            local, remote, LATER + timedelta(hours=1)
        )
        assert status == SyncStatus.CONFLICT
        assert has_changes is True

    def test_both_same_date_different_id(self):
        local = _make_backup_info(date=NOW)
        remote = _make_backup_info(date=NOW)
        status, has_changes = GetBackupsImpl._calculate_sync_status(
            local, remote, EARLIER
        )
        assert status == SyncStatus.CONFLICT
        assert has_changes is False


class TestExecuteOnlyLocal:
    @pytest.mark.asyncio
    async def test_only_local_skips_remote_fetch(self):
        auth = _make_auth()
        cloud_register = MagicMock()
        cloud_register.get_auth = AsyncMock(return_value=auth)
        local_info = BackupsInfo(
            pieces={
                BackupFileType.DATA: _make_backup_info(
                    BackupFileType.DATA, date=EARLIER
                ),
            }
        )
        local_registry = MagicMock()
        local_registry.get_info = AsyncMock(return_value=local_info)
        backup_repo = MagicMock()
        backup_repo.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)

        use_case = GetBackupsImpl(
            backupable_ports={BackupFileType.DATA: backupable},
            backup_repository=backup_repo,
            backup_local_registry=local_registry,
            cloud_register=cloud_register,
        )

        result = await use_case.execute(BackupsInfoRequest(only_local=True))

        assert backup_repo.get_info.call_count == 0
        piece = result.pieces[BackupFileType.DATA]
        assert piece.remote is None
        assert piece.status is None
        assert piece.local is not None

    @pytest.mark.asyncio
    async def test_only_local_returns_local_info(self):
        auth = _make_auth()
        cloud_register = MagicMock()
        cloud_register.get_auth = AsyncMock(return_value=auth)
        local_backup = _make_backup_info(BackupFileType.DATA, date=EARLIER)
        local_info = BackupsInfo(pieces={BackupFileType.DATA: local_backup})
        local_registry = MagicMock()
        local_registry.get_info = AsyncMock(return_value=local_info)
        backup_repo = MagicMock()
        backup_repo.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)

        use_case = GetBackupsImpl(
            backupable_ports={BackupFileType.DATA: backupable},
            backup_repository=backup_repo,
            backup_local_registry=local_registry,
            cloud_register=cloud_register,
        )

        result = await use_case.execute(BackupsInfoRequest(only_local=True))

        assert result.pieces[BackupFileType.DATA].local == local_backup
        assert result.pieces[BackupFileType.DATA].has_local_changes is True


class TestExecuteRemote:
    @pytest.mark.asyncio
    async def test_fetches_remote_when_not_only_local(self):
        auth = _make_auth()
        cloud_register = MagicMock()
        cloud_register.get_auth = AsyncMock(return_value=auth)
        remote_backup = _make_backup_info(BackupFileType.DATA, date=NOW)
        remote_info = BackupsInfo(pieces={BackupFileType.DATA: remote_backup})
        local_registry = MagicMock()
        local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backup_repo = MagicMock()
        backup_repo.get_info = AsyncMock(return_value=remote_info)
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)

        use_case = GetBackupsImpl(
            backupable_ports={BackupFileType.DATA: backupable},
            backup_repository=backup_repo,
            backup_local_registry=local_registry,
            cloud_register=cloud_register,
        )

        result = await use_case.execute(BackupsInfoRequest(only_local=False))

        assert backup_repo.get_info.call_count == 1
        piece = result.pieces[BackupFileType.DATA]
        assert piece.remote == remote_backup
        assert piece.status is not None


class TestExecutePermissions:
    @pytest.mark.asyncio
    async def test_raises_permission_denied_if_missing(self):
        auth = _make_auth(permissions=["other.permission"])
        cloud_register = MagicMock()
        cloud_register.get_auth = AsyncMock(return_value=auth)
        local_registry = MagicMock()
        local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backup_repo = MagicMock()
        backup_repo.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))

        use_case = GetBackupsImpl(
            backupable_ports={},
            backup_repository=backup_repo,
            backup_local_registry=local_registry,
            cloud_register=cloud_register,
        )

        with pytest.raises(PermissionDenied):
            await use_case.execute(BackupsInfoRequest())

    @pytest.mark.asyncio
    async def test_raises_no_user_logged_if_auth_none(self):
        cloud_register = MagicMock()
        cloud_register.get_auth = AsyncMock(return_value=None)
        local_registry = MagicMock()
        local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backup_repo = MagicMock()
        backup_repo.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))

        use_case = GetBackupsImpl(
            backupable_ports={},
            backup_repository=backup_repo,
            backup_local_registry=local_registry,
            cloud_register=cloud_register,
        )

        with pytest.raises(NoUserLogged):
            await use_case.execute(BackupsInfoRequest())


class TestExecuteSkipsMissingPorts:
    @pytest.mark.asyncio
    async def test_skips_backup_types_without_backupable_ports(self):
        auth = _make_auth()
        cloud_register = MagicMock()
        cloud_register.get_auth = AsyncMock(return_value=auth)
        local_registry = MagicMock()
        local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backup_repo = MagicMock()
        backup_repo.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backupable = MagicMock()
        backupable.get_last_updated = AsyncMock(return_value=NOW)

        use_case = GetBackupsImpl(
            backupable_ports={BackupFileType.DATA: backupable},
            backup_repository=backup_repo,
            backup_local_registry=local_registry,
            cloud_register=cloud_register,
        )

        result = await use_case.execute(BackupsInfoRequest(only_local=True))

        assert BackupFileType.DATA in result.pieces
        assert BackupFileType.CONFIG not in result.pieces

    @pytest.mark.asyncio
    async def test_empty_backupable_ports_returns_empty(self):
        auth = _make_auth()
        cloud_register = MagicMock()
        cloud_register.get_auth = AsyncMock(return_value=auth)
        local_registry = MagicMock()
        local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backup_repo = MagicMock()
        backup_repo.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))

        use_case = GetBackupsImpl(
            backupable_ports={},
            backup_repository=backup_repo,
            backup_local_registry=local_registry,
            cloud_register=cloud_register,
        )

        result = await use_case.execute(BackupsInfoRequest())

        assert result.pieces == {}
