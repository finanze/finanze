import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from domain.backup import (
    BackupFileType,
    BackupInfo,
    BackupPieces,
    BackupProcessResult,
    BackupsInfo,
    BackupTransferPiece,
    SyncStatus,
)
from domain.cloud_auth import CloudAuthData, CloudAuthToken, CloudUserRole
from domain.exception.exceptions import BackupTransferFailed

GET_BACKUPS_URL = "/api/v1/cloud/backup"
UPLOAD_URL = "/api/v1/cloud/backup/upload"
IMPORT_URL = "/api/v1/cloud/backup/import"

SIGNUP_URL = "/api/v1/signup"
SETTINGS_URL = "/api/v1/settings"

USERNAME = "testuser"
PASSWORD = "securePass123"

ALL_PERMISSIONS = [
    "backup.info",
    "backup.create",
    "backup.import",
    "backup.erase",
]


def _auth():
    return CloudAuthData(
        role=CloudUserRole.PLUS,
        permissions=ALL_PERMISSIONS,
        token=CloudAuthToken(
            access_token="tok",
            refresh_token="ref",
            token_type="Bearer",
            expires_at=9999999999,
        ),
        email="test@example.com",
    )


def _backup_info(
    bkg_type=BackupFileType.DATA,
    dt=None,
    bkg_id=None,
    size=100,
):
    return BackupInfo(
        id=bkg_id or uuid.uuid4(),
        protocol=1,
        date=dt or datetime.now(timezone.utc),
        type=bkg_type,
        size=size,
    )


class TestGetBackupsRouteValidation:
    @pytest.mark.asyncio
    async def test_returns_401_when_no_cloud_auth(self, client, cloud_register):
        cloud_register.get_auth = AsyncMock(return_value=None)
        response = await client.get(GET_BACKUPS_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_when_no_permission(self, client, cloud_register):
        auth = _auth()
        auth.permissions = ["some.other.permission"]
        cloud_register.get_auth = AsyncMock(return_value=auth)
        response = await client.get(GET_BACKUPS_URL)
        assert response.status_code == 403


class TestGetBackups:
    @pytest.mark.asyncio
    async def test_returns_200_with_pieces(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backupable_ports,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        local_info = _backup_info(BackupFileType.DATA)
        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backup_repository.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        last_update = datetime.now(timezone.utc)
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=last_update
        )
        backupable_ports[BackupFileType.CONFIG].get_last_updated = AsyncMock(
            return_value=last_update
        )

        response = await client.get(GET_BACKUPS_URL)
        assert response.status_code == 200
        body = await response.get_json()
        assert "pieces" in body
        assert "DATA" in body["pieces"]

    @pytest.mark.asyncio
    async def test_sync_status_when_local_matches_remote(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backupable_ports,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        shared_id = uuid.uuid4()
        dt = datetime.now(timezone.utc) - timedelta(hours=1)
        local_info = _backup_info(BackupFileType.DATA, dt=dt, bkg_id=shared_id)
        remote_info = _backup_info(BackupFileType.DATA, dt=dt, bkg_id=shared_id)

        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backup_repository.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: remote_info})
        )
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=dt - timedelta(minutes=10)
        )
        backupable_ports[BackupFileType.CONFIG].get_last_updated = AsyncMock(
            return_value=dt - timedelta(minutes=10)
        )

        response = await client.get(GET_BACKUPS_URL)
        body = await response.get_json()
        data_piece = body["pieces"]["DATA"]
        assert data_piece["status"] == SyncStatus.SYNC.value
        assert data_piece["has_local_changes"] is False

    @pytest.mark.asyncio
    async def test_pending_status_when_local_changed(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backupable_ports,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        shared_id = uuid.uuid4()
        dt = datetime.now(timezone.utc) - timedelta(hours=2)
        local_info = _backup_info(BackupFileType.DATA, dt=dt, bkg_id=shared_id)

        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backup_repository.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=datetime.now(timezone.utc)
        )
        backupable_ports[BackupFileType.CONFIG].get_last_updated = AsyncMock(
            return_value=dt - timedelta(minutes=10)
        )

        response = await client.get(GET_BACKUPS_URL)
        body = await response.get_json()
        data_piece = body["pieces"]["DATA"]
        assert data_piece["status"] == SyncStatus.PENDING.value
        assert data_piece["has_local_changes"] is True

    @pytest.mark.asyncio
    async def test_only_local_skips_remote(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backupable_ports,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        dt = datetime.now(timezone.utc) - timedelta(hours=1)
        local_info = _backup_info(BackupFileType.DATA, dt=dt)

        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=dt - timedelta(minutes=10)
        )
        backupable_ports[BackupFileType.CONFIG].get_last_updated = AsyncMock(
            return_value=dt - timedelta(minutes=10)
        )

        response = await client.get(f"{GET_BACKUPS_URL}?only_local=true")
        assert response.status_code == 200
        body = await response.get_json()
        data_piece = body["pieces"]["DATA"]
        assert data_piece["remote"] is None
        assert data_piece["status"] is None
        backup_repository.get_info.assert_not_awaited()


class TestUploadBackupRouteValidation:
    @pytest.mark.asyncio
    async def test_returns_400_when_types_missing(self, client):
        response = await client.post(UPLOAD_URL, json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_401_when_no_cloud_auth(
        self,
        client,
        cloud_register,
        backup_local_registry,
    ):
        cloud_register.get_auth = AsyncMock(return_value=None)
        backup_local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        response = await client.post(
            UPLOAD_URL,
            json={"types": ["DATA"]},
        )
        assert response.status_code == 401


class TestUploadBackup:
    @pytest.mark.asyncio
    async def test_returns_200_on_success(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backup_processor,
        backupable_ports,
        data_initiator,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        backup_local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backup_repository.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        dt = datetime.now(timezone.utc)
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=dt
        )
        backupable_ports[BackupFileType.DATA].export = AsyncMock(
            return_value=b"database-export-data"
        )
        backup_processor.compile = AsyncMock(
            return_value=BackupProcessResult(payload=b"encrypted", size=9)
        )

        upload_piece = BackupTransferPiece(
            id=uuid.uuid4(),
            protocol=1,
            date=dt,
            type=BackupFileType.DATA,
            payload=b"encrypted",
            size=9,
        )
        backup_repository.upload = AsyncMock(
            return_value=BackupPieces(pieces=[upload_piece])
        )

        response = await client.post(
            UPLOAD_URL,
            json={"types": ["DATA"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert "DATA" in body["pieces"]
        assert body["pieces"]["DATA"]["status"] == SyncStatus.SYNC.value

    @pytest.mark.asyncio
    async def test_export_called_on_backupable(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backup_processor,
        backupable_ports,
        data_initiator,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        backup_local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backup_repository.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        dt = datetime.now(timezone.utc)
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=dt
        )
        backupable_ports[BackupFileType.DATA].export = AsyncMock(return_value=b"data")
        backup_processor.compile = AsyncMock(
            return_value=BackupProcessResult(payload=b"enc", size=3)
        )
        upload_piece = BackupTransferPiece(
            id=uuid.uuid4(),
            protocol=1,
            date=dt,
            type=BackupFileType.DATA,
            payload=b"enc",
            size=3,
        )
        backup_repository.upload = AsyncMock(
            return_value=BackupPieces(pieces=[upload_piece])
        )

        await client.post(UPLOAD_URL, json={"types": ["DATA"]})
        backupable_ports[BackupFileType.DATA].export.assert_awaited_once()
        backup_processor.compile.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_local_registry_updated_after_upload(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backup_processor,
        backupable_ports,
        data_initiator,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        backup_local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backup_repository.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        dt = datetime.now(timezone.utc)
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=dt
        )
        backupable_ports[BackupFileType.DATA].export = AsyncMock(return_value=b"data")
        backup_processor.compile = AsyncMock(
            return_value=BackupProcessResult(payload=b"enc", size=3)
        )
        piece_id = uuid.uuid4()
        upload_piece = BackupTransferPiece(
            id=piece_id,
            protocol=1,
            date=dt,
            type=BackupFileType.DATA,
            payload=b"enc",
            size=3,
        )
        backup_repository.upload = AsyncMock(
            return_value=BackupPieces(pieces=[upload_piece])
        )

        await client.post(UPLOAD_URL, json={"types": ["DATA"]})
        backup_local_registry.insert.assert_awaited_once()
        inserted = backup_local_registry.insert.await_args[0][0]
        assert len(inserted) == 1
        assert inserted[0].id == piece_id

    @pytest.mark.asyncio
    async def test_returns_429_on_cooldown(
        self,
        client,
        cloud_register,
        backup_local_registry,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        recent_info = _backup_info(BackupFileType.DATA, dt=datetime.now(timezone.utc))
        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: recent_info})
        )

        response = await client.post(
            UPLOAD_URL,
            json={"types": ["DATA"]},
        )
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_returns_409_on_conflict(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backupable_ports,
        data_initiator,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        old_dt = datetime.now(timezone.utc) - timedelta(hours=2)
        local_info = _backup_info(BackupFileType.DATA, dt=old_dt)
        remote_info = _backup_info(
            BackupFileType.DATA,
            dt=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backup_repository.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: remote_info})
        )
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=datetime.now(timezone.utc)
        )

        response = await client.post(
            UPLOAD_URL,
            json={"types": ["DATA"]},
        )
        assert response.status_code == 409
        body = await response.get_json()
        assert body["code"] == "BACKUP_CONFLICT"


class TestImportBackupRouteValidation:
    @pytest.mark.asyncio
    async def test_returns_400_when_types_missing(self, client):
        response = await client.post(IMPORT_URL, json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_401_when_no_cloud_auth(
        self,
        client,
        cloud_register,
        backup_local_registry,
    ):
        cloud_register.get_auth = AsyncMock(return_value=None)
        backup_local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        response = await client.post(
            IMPORT_URL,
            json={"types": ["DATA"]},
        )
        assert response.status_code == 401


class TestImportBackup:
    @pytest.mark.asyncio
    async def test_returns_200_on_success(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backup_processor,
        backupable_ports,
        data_initiator,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        local_dt = datetime.now(timezone.utc) - timedelta(hours=3)
        remote_dt = datetime.now(timezone.utc) - timedelta(hours=1)
        local_info = _backup_info(BackupFileType.DATA, dt=local_dt)
        remote_info = _backup_info(BackupFileType.DATA, dt=remote_dt)
        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backup_repository.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: remote_info})
        )
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=local_dt - timedelta(minutes=10)
        )
        downloaded_piece = BackupTransferPiece(
            id=remote_info.id,
            protocol=1,
            date=remote_dt,
            type=BackupFileType.DATA,
            payload=b"encrypted-data",
            size=14,
        )
        backup_repository.download = AsyncMock(
            return_value=BackupPieces(pieces=[downloaded_piece])
        )
        backup_processor.decompile = AsyncMock(
            return_value=BackupProcessResult(payload=b"decrypted-data", size=14)
        )

        response = await client.post(
            IMPORT_URL,
            json={"types": ["DATA"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert "DATA" in body["pieces"]
        assert body["pieces"]["DATA"]["status"] == SyncStatus.SYNC.value

    @pytest.mark.asyncio
    async def test_import_data_called_on_backupable(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backup_processor,
        backupable_ports,
        data_initiator,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        local_dt = datetime.now(timezone.utc) - timedelta(hours=3)
        remote_dt = datetime.now(timezone.utc) - timedelta(hours=1)
        local_info = _backup_info(BackupFileType.DATA, dt=local_dt)
        remote_info = _backup_info(BackupFileType.DATA, dt=remote_dt)
        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backup_repository.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: remote_info})
        )
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=local_dt - timedelta(minutes=10)
        )
        downloaded_piece = BackupTransferPiece(
            id=remote_info.id,
            protocol=1,
            date=remote_dt,
            type=BackupFileType.DATA,
            payload=b"encrypted",
            size=9,
        )
        backup_repository.download = AsyncMock(
            return_value=BackupPieces(pieces=[downloaded_piece])
        )
        backup_processor.decompile = AsyncMock(
            return_value=BackupProcessResult(payload=b"raw-data", size=8)
        )

        await client.post(IMPORT_URL, json={"types": ["DATA"]})
        backupable_ports[BackupFileType.DATA].import_data.assert_awaited_once_with(
            b"raw-data"
        )

    @pytest.mark.asyncio
    async def test_local_registry_updated_after_import(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backup_processor,
        backupable_ports,
        data_initiator,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        local_dt = datetime.now(timezone.utc) - timedelta(hours=3)
        remote_dt = datetime.now(timezone.utc) - timedelta(hours=1)
        local_info = _backup_info(BackupFileType.DATA, dt=local_dt)
        remote_info = _backup_info(BackupFileType.DATA, dt=remote_dt)
        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backup_repository.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: remote_info})
        )
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=local_dt - timedelta(minutes=10)
        )
        downloaded_piece = BackupTransferPiece(
            id=remote_info.id,
            protocol=1,
            date=remote_dt,
            type=BackupFileType.DATA,
            payload=b"enc",
            size=3,
        )
        backup_repository.download = AsyncMock(
            return_value=BackupPieces(pieces=[downloaded_piece])
        )
        backup_processor.decompile = AsyncMock(
            return_value=BackupProcessResult(payload=b"raw", size=3)
        )

        await client.post(IMPORT_URL, json={"types": ["DATA"]})
        backup_local_registry.insert.assert_awaited_once()
        inserted = backup_local_registry.insert.await_args[0][0]
        assert len(inserted) == 1
        assert inserted[0].id == remote_info.id

    @pytest.mark.asyncio
    async def test_returns_429_on_cooldown(
        self,
        client,
        cloud_register,
        backup_local_registry,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        recent_info = _backup_info(BackupFileType.DATA, dt=datetime.now(timezone.utc))
        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: recent_info})
        )

        response = await client.post(
            IMPORT_URL,
            json={"types": ["DATA"]},
        )
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_returns_401_on_invalid_backup_password(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backup_processor,
        backupable_ports,
        data_initiator,
    ):
        from domain.exception.exceptions import InvalidBackupCredentials

        cloud_register.get_auth = AsyncMock(return_value=_auth())
        local_dt = datetime.now(timezone.utc) - timedelta(hours=3)
        remote_dt = datetime.now(timezone.utc) - timedelta(hours=1)
        local_info = _backup_info(BackupFileType.DATA, dt=local_dt)
        remote_info = _backup_info(BackupFileType.DATA, dt=remote_dt)
        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backup_repository.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: remote_info})
        )
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=local_dt - timedelta(minutes=10)
        )
        downloaded_piece = BackupTransferPiece(
            id=remote_info.id,
            protocol=1,
            date=remote_dt,
            type=BackupFileType.DATA,
            payload=b"enc",
            size=3,
        )
        backup_repository.download = AsyncMock(
            return_value=BackupPieces(pieces=[downloaded_piece])
        )
        backup_processor.decompile = AsyncMock(
            side_effect=InvalidBackupCredentials("wrong password")
        )

        response = await client.post(
            IMPORT_URL,
            json={"types": ["DATA"], "password": "wrong-password"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_skips_already_synced_piece(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backupable_ports,
        data_initiator,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        shared_id = uuid.uuid4()
        dt = datetime.now(timezone.utc) - timedelta(hours=1)
        local_info = _backup_info(BackupFileType.DATA, dt=dt, bkg_id=shared_id)
        remote_info = _backup_info(BackupFileType.DATA, dt=dt, bkg_id=shared_id)

        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backup_repository.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: remote_info})
        )
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=dt - timedelta(minutes=10)
        )
        backup_repository.download = AsyncMock(return_value=BackupPieces(pieces=[]))

        response = await client.post(
            IMPORT_URL,
            json={"types": ["DATA"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["pieces"] == {}

    @pytest.mark.asyncio
    async def test_returns_409_on_conflict_with_local_changes(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backupable_ports,
        data_initiator,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        old_dt = datetime.now(timezone.utc) - timedelta(hours=2)
        local_info = _backup_info(BackupFileType.DATA, dt=old_dt)
        remote_info = _backup_info(
            BackupFileType.DATA,
            dt=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backup_repository.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: remote_info})
        )
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=datetime.now(timezone.utc)
        )

        response = await client.post(
            IMPORT_URL,
            json={"types": ["DATA"]},
        )
        assert response.status_code == 409
        body = await response.get_json()
        assert body["code"] == "BACKUP_CONFLICT"


class TestUploadMultipleTypes:
    @pytest.mark.asyncio
    async def test_upload_data_and_config(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backup_processor,
        backupable_ports,
        data_initiator,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        backup_local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backup_repository.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        dt = datetime.now(timezone.utc)
        for port in backupable_ports.values():
            port.get_last_updated = AsyncMock(return_value=dt)
            port.export = AsyncMock(return_value=b"export-bytes")

        backup_processor.compile = AsyncMock(
            return_value=BackupProcessResult(payload=b"enc", size=3)
        )
        data_piece = BackupTransferPiece(
            id=uuid.uuid4(),
            protocol=1,
            date=dt,
            type=BackupFileType.DATA,
            payload=b"enc",
            size=3,
        )
        config_piece = BackupTransferPiece(
            id=uuid.uuid4(),
            protocol=1,
            date=dt,
            type=BackupFileType.CONFIG,
            payload=b"enc",
            size=3,
        )
        backup_repository.upload = AsyncMock(
            return_value=BackupPieces(pieces=[data_piece, config_piece])
        )

        response = await client.post(
            UPLOAD_URL,
            json={"types": ["DATA", "CONFIG"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert "DATA" in body["pieces"]
        assert "CONFIG" in body["pieces"]
        assert body["pieces"]["DATA"]["status"] == SyncStatus.SYNC.value
        assert body["pieces"]["CONFIG"]["status"] == SyncStatus.SYNC.value


class TestBackupTransferFailed:
    @pytest.mark.asyncio
    async def test_import_returns_502_when_download_fails(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backupable_ports,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        local_dt = datetime.now(timezone.utc) - timedelta(hours=3)
        remote_dt = datetime.now(timezone.utc) - timedelta(hours=1)
        local_info = _backup_info(BackupFileType.DATA, dt=local_dt)
        remote_info = _backup_info(BackupFileType.DATA, dt=remote_dt)
        backup_local_registry.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: local_info})
        )
        backup_repository.get_info = AsyncMock(
            return_value=BackupsInfo(pieces={BackupFileType.DATA: remote_info})
        )
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=local_dt - timedelta(minutes=10)
        )
        backup_repository.download = AsyncMock(
            side_effect=BackupTransferFailed("Failed to download backup piece DATA")
        )

        response = await client.post(IMPORT_URL, json={"types": ["DATA"]})
        assert response.status_code == 502
        body = await response.get_json()
        assert body["code"] == "BACKUP_TRANSFER_FAILED"

    @pytest.mark.asyncio
    async def test_upload_returns_502_when_upload_fails(
        self,
        client,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backup_processor,
        backupable_ports,
        data_initiator,
    ):
        cloud_register.get_auth = AsyncMock(return_value=_auth())
        backup_local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        backup_repository.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
        dt = datetime.now(timezone.utc)
        backupable_ports[BackupFileType.DATA].get_last_updated = AsyncMock(
            return_value=dt
        )
        backupable_ports[BackupFileType.DATA].export = AsyncMock(
            return_value=b"export-bytes"
        )
        backup_processor.compile = AsyncMock(
            return_value=BackupProcessResult(payload=b"enc", size=3)
        )
        backup_repository.upload = AsyncMock(
            side_effect=BackupTransferFailed("Failed to upload backup piece DATA")
        )

        response = await client.post(UPLOAD_URL, json={"types": ["DATA"]})
        assert response.status_code == 502
        body = await response.get_json()
        assert body["code"] == "BACKUP_TRANSFER_FAILED"
