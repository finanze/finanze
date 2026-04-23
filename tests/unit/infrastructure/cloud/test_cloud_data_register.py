import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
import pytest_asyncio

from domain.backup import BackupFileType, BackupInfo, BackupMode, BackupSettings
from domain.cloud_auth import CloudAuthToken, CloudUserRole
from domain.exception.exceptions import InvalidToken, NoUserLogged
from domain.user import User
from infrastructure.cloud.cloud_data_register import CloudDataRegister


def _make_user(tmp_path: Path) -> User:
    return User(
        id=uuid4(),
        username="testuser",
        path=tmp_path,
        last_login=None,
    )


def _make_token() -> CloudAuthToken:
    return CloudAuthToken(
        access_token="test_access",
        refresh_token="test_refresh",
        token_type="Bearer",
        expires_at=9999999999,
    )


TEST_JWT_SECRET = "test-secret-key-that-is-at-least-32-bytes!"


def _make_jwt(email="user@example.com", role="PLUS", permissions=None):
    payload = {"email": email}
    if role is not None:
        payload["user_role"] = role
    if permissions is not None:
        payload["permissions"] = permissions
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest_asyncio.fixture
async def register():
    reg = CloudDataRegister()
    yield reg
    try:
        await reg._load_cloud_data.cache.clear()
    except Exception:
        pass
    try:
        await reg.decode_token.cache.clear()
    except Exception:
        pass


class TestCheckConnected:
    @pytest.mark.asyncio
    async def test_raises_no_user_logged_before_connect(self, register):
        with pytest.raises(NoUserLogged):
            await register.get_info()

    @pytest.mark.asyncio
    async def test_check_connected_method_raises(self, register):
        with pytest.raises(NoUserLogged):
            register._check_connected()


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_creates_cloud_json(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        cloud_file = tmp_path / "cloud.json"
        assert cloud_file.is_file()

        with open(cloud_file, "r") as f:
            data = json.load(f)
        assert data == {"backup": {}, "auth": None}

    @pytest.mark.asyncio
    async def test_connect_does_not_overwrite_existing(self, register, tmp_path):
        cloud_file = tmp_path / "cloud.json"
        existing_data = {"backup": {"custom": True}, "auth": "something"}
        with open(cloud_file, "w") as f:
            json.dump(existing_data, f)

        user = _make_user(tmp_path)
        await register.connect(user)

        with open(cloud_file, "r") as f:
            data = json.load(f)
        assert data == existing_data


class TestGetInfo:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_backups(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        info = await register.get_info()
        assert info.pieces == {}

    @pytest.mark.asyncio
    async def test_returns_backup_info_after_insert(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        backup_id = uuid4()
        now = datetime.now().astimezone()
        entry = BackupInfo(
            id=backup_id,
            protocol=1,
            date=now,
            type=BackupFileType.DATA,
            size=1024,
        )
        await register.insert([entry])

        info = await register.get_info()
        assert BackupFileType.DATA in info.pieces
        piece = info.pieces[BackupFileType.DATA]
        assert piece.id == backup_id
        assert piece.protocol == 1
        assert piece.size == 1024
        assert piece.type == BackupFileType.DATA


class TestInsert:
    @pytest.mark.asyncio
    async def test_insert_multiple_types(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        now = datetime.now().astimezone()
        entries = [
            BackupInfo(
                id=uuid4(), protocol=1, date=now, type=BackupFileType.DATA, size=100
            ),
            BackupInfo(
                id=uuid4(), protocol=1, date=now, type=BackupFileType.CONFIG, size=200
            ),
        ]
        await register.insert(entries)

        info = await register.get_info()
        assert len(info.pieces) == 2
        assert BackupFileType.DATA in info.pieces
        assert BackupFileType.CONFIG in info.pieces

    @pytest.mark.asyncio
    async def test_insert_overwrites_existing_type(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        now = datetime.now().astimezone()
        first = BackupInfo(
            id=uuid4(), protocol=1, date=now, type=BackupFileType.DATA, size=100
        )
        await register.insert([first])

        second_id = uuid4()
        second = BackupInfo(
            id=second_id, protocol=1, date=now, type=BackupFileType.DATA, size=500
        )
        await register.insert([second])

        info = await register.get_info()
        assert info.pieces[BackupFileType.DATA].id == second_id
        assert info.pieces[BackupFileType.DATA].size == 500


class TestAuthToken:
    @pytest.mark.asyncio
    async def test_save_and_get_auth_token(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        token = _make_token()
        await register.save_auth(token)

        retrieved = await register.get_auth_token()
        assert retrieved is not None
        assert retrieved.access_token == "test_access"
        assert retrieved.refresh_token == "test_refresh"
        assert retrieved.token_type == "Bearer"
        assert retrieved.expires_at == 9999999999

    @pytest.mark.asyncio
    async def test_get_auth_token_returns_none_when_no_auth(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        token = await register.get_auth_token()
        assert token is None


class TestGetAuth:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_token(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        auth = await register.get_auth()
        assert auth is None

    @pytest.mark.asyncio
    async def test_returns_auth_data_with_decoded_token(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        jwt_token = _make_jwt(
            email="user@test.com", role="PLUS", permissions=["backup.info"]
        )
        token = CloudAuthToken(
            access_token=jwt_token,
            refresh_token="refresh",
            token_type="Bearer",
            expires_at=9999999999,
        )
        await register.save_auth(token)

        auth = await register.get_auth()
        assert auth is not None
        assert auth.email == "user@test.com"
        assert auth.role == CloudUserRole.PLUS
        assert auth.permissions == ["backup.info"]
        assert auth.token.access_token == jwt_token


class TestClearAuth:
    @pytest.mark.asyncio
    async def test_clear_auth_removes_data(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        token = _make_token()
        await register.save_auth(token)
        assert await register.get_auth_token() is not None

        await register.clear_auth()
        assert await register.get_auth_token() is None


class TestDecodeToken:
    @pytest.mark.asyncio
    async def test_decodes_valid_jwt(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        jwt_token = _make_jwt(
            email="test@example.com",
            role="PLUS",
            permissions=["backup.info", "backup.create"],
        )
        result = await register.decode_token(jwt_token)

        assert result.email == "test@example.com"
        assert result.role == CloudUserRole.PLUS
        assert result.permissions == ["backup.info", "backup.create"]

    @pytest.mark.asyncio
    async def test_decode_token_defaults_role_to_none(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        payload = {"email": "test@example.com"}
        jwt_token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        result = await register.decode_token(jwt_token)

        assert result.role == CloudUserRole.NONE

    @pytest.mark.asyncio
    async def test_decode_token_invalid_role_defaults_to_none(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        payload = {"email": "test@example.com", "user_role": "INVALID_ROLE"}
        jwt_token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        result = await register.decode_token(jwt_token)

        assert result.role == CloudUserRole.NONE

    @pytest.mark.asyncio
    async def test_decode_token_missing_email_raises(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        payload = {"user_role": "PLUS"}
        jwt_token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        with pytest.raises(InvalidToken):
            await register.decode_token(jwt_token)

    @pytest.mark.asyncio
    async def test_decode_token_malformed_raises(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        with pytest.raises(InvalidToken, match="malformed"):
            await register.decode_token("not.a.valid.jwt.token.at.all")

    @pytest.mark.asyncio
    async def test_decode_token_non_list_permissions_defaults_to_empty(
        self, register, tmp_path
    ):
        user = _make_user(tmp_path)
        await register.connect(user)

        payload = {"email": "test@example.com", "permissions": "not_a_list"}
        jwt_token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        result = await register.decode_token(jwt_token)

        assert result.permissions == []


class TestBackupSettings:
    @pytest.mark.asyncio
    async def test_default_settings_is_manual(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        settings = await register.get_backup_settings()
        assert settings.mode == BackupMode.MANUAL

    @pytest.mark.asyncio
    async def test_save_and_get_backup_settings(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        await register.save_backup_settings(BackupSettings(mode=BackupMode.AUTO))
        settings = await register.get_backup_settings()
        assert settings.mode == BackupMode.AUTO

    @pytest.mark.asyncio
    async def test_invalid_mode_defaults_to_manual(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)

        cloud_file = tmp_path / "cloud.json"
        with open(cloud_file, "r") as f:
            data = json.load(f)
        data["backup"] = {"settings": {"mode": "INVALID"}}
        with open(cloud_file, "w") as f:
            json.dump(data, f)
        await register._load_cloud_data.cache.clear()

        settings = await register.get_backup_settings()
        assert settings.mode == BackupMode.MANUAL


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_clears_cloud_file(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)
        assert register._cloud_file is not None

        await register.disconnect()
        assert register._cloud_file is None

    @pytest.mark.asyncio
    async def test_disconnect_makes_operations_fail(self, register, tmp_path):
        user = _make_user(tmp_path)
        await register.connect(user)
        await register.disconnect()

        with pytest.raises(NoUserLogged):
            await register.get_info()
