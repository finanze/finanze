import hashlib
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.use_cases.change_user_password import ChangeUserPasswordImpl
from application.use_cases.import_backup import ImportBackupImpl
from domain.backup import (
    BackupFileType,
    BackupInfo,
    BackupPieces,
    BackupProcessResult,
    BackupsInfo,
    BackupTransferPiece,
    ImportBackupRequest,
)
from domain.cloud_auth import CloudAuthData, CloudAuthToken, CloudUserRole
from domain.data_init import DatasourceInitContext, DatasourceInitParams
from domain.user import User
from domain.user_login import ChangePasswordRequest
from infrastructure.config.file_legacy_config_source import FileLegacyConfigSource
from infrastructure.config.legacy_config_backup_importer import (
    LegacyConfigBackupImporter,
)
from infrastructure.repository.db import manager as manager_module
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.manager import DBManager
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.settings.settings_mapper import legacy_to_sections
from infrastructure.repository.settings.settings_repository import SettingsRepository
from tests.legacy_config_samples import (
    BROKEN_DESKTOP_SAMPLES,
    DESKTOP_SAMPLES,
    assert_same_settings,
    custom_settings,
    default_settings,
    labeling_settings,
    parse_sample,
    pre07_integrations_settings,
    read_sample,
    v6_settings,
)

SETTINGS_MIGRATION = "v0.11.0:4_settings"
VERSION_NAMES = [v.name for v in versions]
PRE_SETTINGS_VERSIONS = versions[: VERSION_NAMES.index(SETTINGS_MIGRATION)]
PRE_INTEGRATIONS_VERSIONS = versions[
    : VERSION_NAMES.index("v0.7.0:2_external_integrations_migration")
]

PASSWORD = "securePass123"
NEW_PASSWORD = "newPass456!"


def _user(path) -> User:
    path.mkdir(parents=True, exist_ok=True)
    return User(id=uuid4(), username=path.name, path=path, last_login=None)


async def _create_legacy_db(
    monkeypatch, user: User, registry=PRE_SETTINGS_VERSIONS, statements=()
):
    with monkeypatch.context() as patch:
        patch.setattr(manager_module, "versions", registry)
        if "v0.8.0:0_sys_config" not in {v.name for v in registry}:
            patch.setattr(DBClient, "_update_last_update_date", AsyncMock())
        client = DBClient()
        manager = DBManager(client)
        await manager.initialize(
            DatasourceInitParams.build(user=user, password=PASSWORD)
        )
        async with client.tx(skip_last_update=True) as cursor:
            for statement in statements:
                await cursor.execute(statement)
        await manager.lock()


async def _export_legacy_db(monkeypatch, user: User) -> bytes:
    monkeypatch.setattr(manager_module, "versions", PRE_SETTINGS_VERSIONS)
    try:
        manager = DBManager(DBClient())
        await manager.initialize(
            DatasourceInitParams.build(user=user, password=PASSWORD)
        )
        data = await manager.export()
        await manager.lock()
        return data
    finally:
        monkeypatch.setattr(manager_module, "versions", versions)


async def _login(user: User, password: str = PASSWORD):
    client = DBClient()
    manager = DBManager(client)
    repository = SettingsRepository(client, FileLegacyConfigSource())
    await repository.connect(user)
    await manager.initialize(
        DatasourceInitParams(
            user=user,
            password=password,
            context=DatasourceInitContext(config=repository),
        )
    )
    return manager, repository, client


async def _applied_migrations(client: DBClient) -> set[str]:
    async with client.read() as cursor:
        await cursor.execute("SELECT name FROM migrations")
        return {row[0] for row in await cursor.fetchall()}


async def _settings_row_count(client: DBClient) -> int:
    async with client.read() as cursor:
        await cursor.execute("SELECT COUNT(*) FROM settings")
        return (await cursor.fetchone())[0]


class TestLoginUpgrade:
    @pytest.mark.parametrize("sample", DESKTOP_SAMPLES, ids=str)
    @pytest.mark.asyncio
    async def test_existing_user_gets_legacy_config_migrated(
        self, tmp_path, monkeypatch, sample
    ):
        user = _user(tmp_path / "user")
        await _create_legacy_db(monkeypatch, user)
        content = read_sample(sample.name)
        (user.path / "config.yml").write_text(content)

        manager, repository, client = await _login(user)

        assert SETTINGS_MIGRATION in await _applied_migrations(client)
        assert_same_settings(await repository.load(), sample.expected())
        assert (user.path / "config.yml").read_text() == content
        await manager.lock()

    @pytest.mark.parametrize("name", BROKEN_DESKTOP_SAMPLES)
    @pytest.mark.asyncio
    async def test_broken_legacy_config_does_not_block_login(
        self, tmp_path, monkeypatch, name
    ):
        user = _user(tmp_path / "user")
        await _create_legacy_db(monkeypatch, user)
        (user.path / "config.yml").write_text(read_sample(name))

        manager, repository, client = await _login(user)

        assert manager.unlocked
        assert await _settings_row_count(client) == 0
        assert_same_settings(await repository.load(), default_settings())
        await manager.lock()

    @pytest.mark.asyncio
    async def test_existing_user_without_config_file_gets_defaults(
        self, tmp_path, monkeypatch
    ):
        user = _user(tmp_path / "user")
        await _create_legacy_db(monkeypatch, user)

        manager, repository, client = await _login(user)

        assert await _settings_row_count(client) == 0
        assert_same_settings(await repository.load(), default_settings())
        assert not (user.path / "config.yml").exists()
        await manager.lock()

    @pytest.mark.asyncio
    async def test_failing_config_port_does_not_block_login(
        self, tmp_path, monkeypatch
    ):
        user = _user(tmp_path / "user")
        await _create_legacy_db(monkeypatch, user)
        config_port = MagicMock()
        config_port.load_legacy = AsyncMock(side_effect=RuntimeError("boom"))
        manager = DBManager(DBClient())

        await manager.initialize(
            DatasourceInitParams(
                user=user,
                password=PASSWORD,
                context=DatasourceInitContext(config=config_port),
            )
        )

        assert manager.unlocked
        await manager.lock()

    @pytest.mark.asyncio
    async def test_legacy_config_is_migrated_only_once(self, tmp_path, monkeypatch):
        user = _user(tmp_path / "user")
        await _create_legacy_db(monkeypatch, user)
        (user.path / "config.yml").write_text(read_sample("desktop_v8_custom.yml"))
        manager, repository, _ = await _login(user)
        await manager.lock()

        (user.path / "config.yml").write_text(read_sample("desktop_v8_labeling.yml"))
        manager, repository, _ = await _login(user)

        assert_same_settings(await repository.load(), custom_settings())
        await manager.lock()

    @pytest.mark.asyncio
    async def test_fresh_user_gets_defaults_without_config_file(self, tmp_path):
        user = _user(tmp_path / "user")

        manager, repository, client = await _login(user)

        assert SETTINGS_MIGRATION in await _applied_migrations(client)
        assert await _settings_row_count(client) == 0
        assert_same_settings(await repository.load(), default_settings())
        assert not (user.path / "config.yml").exists()
        await manager.lock()

    @pytest.mark.asyncio
    async def test_saved_settings_survive_relogin(self, tmp_path):
        user = _user(tmp_path / "user")
        manager, repository, _ = await _login(user)
        await repository.save(labeling_settings())
        await manager.lock()

        manager, repository, _ = await _login(user)

        assert_same_settings(await repository.load(), labeling_settings())
        assert not (user.path / "config.yml").exists()
        await manager.lock()

    @pytest.mark.asyncio
    async def test_pre_07_user_gets_integrations_and_settings_migrated(
        self, tmp_path, monkeypatch
    ):
        user = _user(tmp_path / "user")
        await _create_legacy_db(
            monkeypatch,
            user,
            PRE_INTEGRATIONS_VERSIONS,
            [
                "UPDATE external_integrations SET status = 'ON' WHERE id = 'GOOGLE_SHEETS'"
            ],
        )
        (user.path / "config.yml").write_text(
            read_sample("desktop_pre07_integrations.yml")
        )

        manager, repository, client = await _login(user)

        async with client.read() as cursor:
            await cursor.execute(
                "SELECT payload FROM external_integrations WHERE id = 'GOOGLE_SHEETS'"
            )
            payload = (await cursor.fetchone())[0]
        assert "sheets-client-id" in payload
        assert_same_settings(await repository.load(), pre07_integrations_settings())
        await manager.lock()


class TestChangePasswordUpgrade:
    @pytest.mark.asyncio
    async def test_change_password_migrates_legacy_config(self, tmp_path, monkeypatch):
        user = _user(tmp_path / "user")
        await _create_legacy_db(monkeypatch, user)
        (user.path / "config.yml").write_text(read_sample("desktop_v8_custom.yml"))
        client = DBClient()
        manager = DBManager(client)
        repository = SettingsRepository(client, FileLegacyConfigSource())
        data_manager = MagicMock()
        data_manager.get_user = AsyncMock(return_value=user)

        await ChangeUserPasswordImpl(manager, data_manager, repository).execute(
            ChangePasswordRequest(
                username=user.username,
                old_password=PASSWORD,
                new_password=NEW_PASSWORD,
            )
        )
        (user.path / "config.yml").unlink()

        manager, repository, client = await _login(user, NEW_PASSWORD)

        assert_same_settings(await repository.load(), custom_settings())
        await manager.lock()


def _auth():
    return CloudAuthData(
        role=CloudUserRole.PLUS,
        permissions=["backup.import"],
        token=CloudAuthToken(
            access_token="a",
            refresh_token="r",
            token_type="bearer",
            expires_at=9999999999,
        ),
        email="test@test.com",
    )


def _remote(pieces: dict[BackupFileType, bytes]):
    transfer = []
    infos = {}
    for backup_type, payload in pieces.items():
        piece_id = uuid4()
        info = BackupInfo(
            id=piece_id,
            protocol=1,
            date=datetime.now().astimezone(),
            type=backup_type,
            size=len(payload),
        )
        infos[backup_type] = info
        transfer.append(
            BackupTransferPiece(
                id=piece_id,
                protocol=1,
                date=info.date,
                type=backup_type,
                payload=payload,
                size=len(payload),
            )
        )
    return BackupsInfo(pieces=infos), transfer


def _import_backup_uc(manager: DBManager, repository: SettingsRepository, pieces):
    remote_info, transfer = _remote(pieces)

    async def _download(params):
        return BackupPieces(pieces=[p for p in transfer if p.type in params.types])

    async def _decompile(request):
        return BackupProcessResult(payload=request.payload, size=len(request.payload))

    cloud_register = MagicMock()
    cloud_register.get_auth = AsyncMock(return_value=_auth())
    backup_repository = MagicMock()
    backup_repository.get_info = AsyncMock(return_value=remote_info)
    backup_repository.download = AsyncMock(side_effect=_download)
    local_registry = MagicMock()
    local_registry.get_info = AsyncMock(return_value=BackupsInfo(pieces={}))
    local_registry.insert = AsyncMock()
    processor = MagicMock()
    processor.decompile = AsyncMock(side_effect=_decompile)
    error_reporter = MagicMock()

    use_case = ImportBackupImpl(
        data_initiator=manager,
        backupable_ports={BackupFileType.DATA: manager},
        backup_processor=processor,
        backup_repository=backup_repository,
        backup_local_registry=local_registry,
        cloud_register=cloud_register,
        legacy_config_importer=LegacyConfigBackupImporter(repository),
        error_reporter=error_reporter,
    )
    return use_case, error_reporter


class TestBackupImportUpgrade:
    @pytest.mark.asyncio
    async def test_old_data_backup_keeps_current_settings(self, tmp_path, monkeypatch):
        old_backup = await _export_legacy_db(monkeypatch, _user(tmp_path / "old"))
        user = _user(tmp_path / "user")
        manager, repository, client = await _login(user)
        await repository.save(custom_settings())

        await manager.import_data(old_backup)

        assert SETTINGS_MIGRATION in await _applied_migrations(client)
        assert_same_settings(await repository.load(), custom_settings())
        assert not (user.path / "data.db.tmp").exists()
        await manager.lock()

    @pytest.mark.asyncio
    async def test_new_data_backup_brings_its_settings(self, tmp_path):
        source_user = _user(tmp_path / "source")
        source_manager, source_repository, _ = await _login(source_user)
        await source_repository.save(labeling_settings())
        new_backup = await source_manager.export()
        await source_manager.lock()
        user = _user(tmp_path / "user")
        manager, repository, _ = await _login(user)
        await repository.save(custom_settings())

        await manager.import_data(new_backup)

        assert_same_settings(await repository.load(), labeling_settings())
        await manager.lock()

    @pytest.mark.asyncio
    async def test_initial_import_of_old_backup_then_legacy_config(
        self, tmp_path, monkeypatch
    ):
        old_backup = await _export_legacy_db(monkeypatch, _user(tmp_path / "old"))
        user = _user(tmp_path / "user")
        client = DBClient()
        manager = DBManager(client)
        repository = SettingsRepository(client, FileLegacyConfigSource())

        await manager.import_data(
            old_backup, initialize=True, user=user, password=PASSWORD
        )
        assert await _settings_row_count(client) == 0
        await LegacyConfigBackupImporter(repository).import_data(
            read_sample("desktop_v8_custom.yml").encode()
        )

        assert_same_settings(await repository.load(), custom_settings())
        await manager.lock()

    @pytest.mark.asyncio
    async def test_old_cloud_backup_restores_newer_legacy_config(
        self, tmp_path, monkeypatch
    ):
        old_backup = await _export_legacy_db(monkeypatch, _user(tmp_path / "old"))
        user = _user(tmp_path / "user")
        manager, repository, _ = await _login(user)
        await repository.apply_legacy(
            *legacy_to_sections(parse_sample("desktop_v6.yml"))
        )
        use_case, error_reporter = _import_backup_uc(
            manager,
            repository,
            {
                BackupFileType.DATA: old_backup,
                BackupFileType.CONFIG: read_sample("desktop_v8_labeling.yml").encode(),
            },
        )

        result = await use_case.execute(
            ImportBackupRequest(types=[BackupFileType.DATA], password=None, force=True)
        )

        assert set(result.pieces) == {BackupFileType.DATA}
        assert_same_settings(await repository.load(), labeling_settings())
        error_reporter.capture_exception.assert_not_called()
        await manager.lock()

    @pytest.mark.asyncio
    async def test_stale_cloud_legacy_config_does_not_override_settings(
        self, tmp_path, monkeypatch
    ):
        old_backup = await _export_legacy_db(monkeypatch, _user(tmp_path / "old"))
        user = _user(tmp_path / "user")
        manager, repository, _ = await _login(user)
        await repository.save(custom_settings())
        use_case, error_reporter = _import_backup_uc(
            manager,
            repository,
            {
                BackupFileType.DATA: old_backup,
                BackupFileType.CONFIG: read_sample("desktop_v8_labeling.yml").encode(),
            },
        )

        await use_case.execute(
            ImportBackupRequest(types=[BackupFileType.DATA], password=None, force=True)
        )

        assert_same_settings(await repository.load(), custom_settings())
        error_reporter.capture_exception.assert_not_called()
        await manager.lock()

    @pytest.mark.asyncio
    async def test_corrupted_cloud_legacy_config_is_reported_not_raised(
        self, tmp_path, monkeypatch
    ):
        old_backup = await _export_legacy_db(monkeypatch, _user(tmp_path / "old"))
        user = _user(tmp_path / "user")
        manager, repository, _ = await _login(user)
        await repository.apply_legacy(
            *legacy_to_sections(parse_sample("desktop_v6.yml"))
        )
        use_case, error_reporter = _import_backup_uc(
            manager,
            repository,
            {
                BackupFileType.DATA: old_backup,
                BackupFileType.CONFIG: b"- not\n- a mapping\n",
            },
        )

        result = await use_case.execute(
            ImportBackupRequest(types=[BackupFileType.DATA], password=None, force=True)
        )

        assert set(result.pieces) == {BackupFileType.DATA}
        assert_same_settings(await repository.load(), v6_settings())
        error_reporter.capture_exception.assert_called_once()
        await manager.lock()

    @pytest.mark.asyncio
    async def test_new_device_restore_applies_legacy_config(
        self, tmp_path, monkeypatch
    ):
        old_backup = await _export_legacy_db(monkeypatch, _user(tmp_path / "old"))
        user = _user(tmp_path / "user")
        client = DBClient()
        manager = DBManager(client)
        manager.set_user(user)
        repository = SettingsRepository(client, FileLegacyConfigSource())
        use_case, _ = _import_backup_uc(
            manager,
            repository,
            {
                BackupFileType.DATA: old_backup,
                BackupFileType.CONFIG: read_sample("desktop_v8_custom.yml").encode(),
            },
        )

        await use_case.execute(
            ImportBackupRequest(
                types=[BackupFileType.DATA],
                password=PASSWORD,
                force=True,
                initialize=True,
            )
        )

        assert manager.unlocked
        assert (
            await manager.get_hashed_password()
            == hashlib.sha3_256(PASSWORD.encode()).hexdigest()
        )
        assert_same_settings(await repository.load(), custom_settings())
        await manager.lock()
