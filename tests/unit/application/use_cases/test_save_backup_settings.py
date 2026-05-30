import pytest
from unittest.mock import AsyncMock

from application.use_cases.save_backup_settings import SaveBackupSettingsImpl
from domain.backup import BackupSettings, BackupMode
from domain.cloud_auth import (
    CloudAuthData,
    CloudAuthToken,
    CloudUserRole,
)
from domain.exception.exceptions import PermissionDenied, NoUserLogged


def _make_auth(permissions=None):
    return CloudAuthData(
        role=CloudUserRole.PLUS,
        permissions=permissions or [],
        token=CloudAuthToken(
            access_token="tok",
            refresh_token="ref",
            token_type="Bearer",
            expires_at=0,
        ),
        email="user@example.com",
    )


class TestSaveBackupSettingsManual:
    @pytest.mark.asyncio
    async def test_saves_manual_mode(self):
        port = AsyncMock()
        register = AsyncMock()
        uc = SaveBackupSettingsImpl(backup_settings_port=port, cloud_register=register)

        settings = BackupSettings(mode=BackupMode.MANUAL)
        result = await uc.execute(settings)

        assert result.mode == BackupMode.MANUAL
        port.save_backup_settings.assert_called_once_with(settings)
        register.get_auth.assert_not_called()

    @pytest.mark.asyncio
    async def test_saves_off_mode(self):
        port = AsyncMock()
        register = AsyncMock()
        uc = SaveBackupSettingsImpl(backup_settings_port=port, cloud_register=register)

        settings = BackupSettings(mode=BackupMode.OFF)
        result = await uc.execute(settings)

        assert result.mode == BackupMode.OFF
        port.save_backup_settings.assert_called_once_with(settings)
        register.get_auth.assert_not_called()


class TestSaveBackupSettingsAuto:
    @pytest.mark.asyncio
    async def test_saves_auto_mode_with_permission(self):
        port = AsyncMock()
        register = AsyncMock()
        register.get_auth.return_value = _make_auth(permissions=["backup.auto"])
        uc = SaveBackupSettingsImpl(backup_settings_port=port, cloud_register=register)

        settings = BackupSettings(mode=BackupMode.AUTO)
        result = await uc.execute(settings)

        assert result.mode == BackupMode.AUTO
        port.save_backup_settings.assert_called_once_with(settings)

    @pytest.mark.asyncio
    async def test_rejects_auto_mode_without_permission(self):
        port = AsyncMock()
        register = AsyncMock()
        register.get_auth.return_value = _make_auth(permissions=["backup.create"])
        uc = SaveBackupSettingsImpl(backup_settings_port=port, cloud_register=register)

        settings = BackupSettings(mode=BackupMode.AUTO)

        with pytest.raises(PermissionDenied):
            await uc.execute(settings)

        port.save_backup_settings.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_auto_mode_with_no_auth(self):
        port = AsyncMock()
        register = AsyncMock()
        register.get_auth.return_value = None
        uc = SaveBackupSettingsImpl(backup_settings_port=port, cloud_register=register)

        settings = BackupSettings(mode=BackupMode.AUTO)

        with pytest.raises(NoUserLogged):
            await uc.execute(settings)

        port.save_backup_settings.assert_not_called()
