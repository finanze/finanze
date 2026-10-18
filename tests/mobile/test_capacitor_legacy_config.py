import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio

from domain.backup import BackupFileType
from domain.data_init import DatasourceInitContext
from domain.user import User
from infrastructure.cloud.backup.staging_registry import get_file_name
from infrastructure.config.capacitor_legacy_config_backup_importer import (
    CapacitorLegacyConfigBackupImporter,
)
from infrastructure.config.capacitor_legacy_config_source import (
    CapacitorLegacyConfigSource,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v11.v0110_4_settings import (
    V01104Settings,
)
from infrastructure.repository.settings.settings_repository import SettingsRepository
from tests.legacy_config_samples import (
    BROKEN_MOBILE_SAMPLES,
    MOBILE_SAMPLES,
    V8_LAST_UPDATE,
    assert_same_settings,
    custom_settings,
    default_settings,
    labeling_settings,
    mobile_backup_payload,
    parse_sample,
    read_sample,
)

DECOMPILED_CONFIG = get_file_name(BackupFileType.CONFIG, "decompiled")


def _user() -> User:
    return User(id=uuid4(), username="mobile", path=Path("."), last_login=None)


def _prefs_key(user: User) -> str:
    return f"config:{user.hashed_id()}"


def _client() -> tuple[DBClient, sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "INSERT INTO sys_config (key, value) VALUES ('last_update', ?)",
        ("2000-01-01T00:00:00+00:00",),
    )
    conn.commit()
    return DBClient(conn), conn


async def _migrate(client: DBClient, config) -> None:
    async with client.tx(skip_last_update=True) as cursor:
        await V01104Settings().upgrade(cursor, DatasourceInitContext(config=config))


@pytest_asyncio.fixture
async def repository():
    client, conn = _client()
    await _migrate(client, None)
    yield SettingsRepository(client, CapacitorLegacyConfigSource())
    conn.close()


class TestCapacitorLegacyConfigSource:
    @pytest.mark.parametrize("sample", MOBILE_SAMPLES, ids=str)
    @pytest.mark.asyncio
    async def test_loads_preferences_payload(self, preferences, sample):
        user = _user()
        preferences.values[_prefs_key(user)] = read_sample(sample.name)
        source = CapacitorLegacyConfigSource()
        await source.connect(user)

        assert await source.load() == parse_sample(sample.name)

    @pytest.mark.parametrize("name", BROKEN_MOBILE_SAMPLES)
    @pytest.mark.asyncio
    async def test_broken_payload_returns_none(self, preferences, name):
        user = _user()
        preferences.values[_prefs_key(user)] = read_sample(name)
        source = CapacitorLegacyConfigSource()
        await source.connect(user)

        assert await source.load() is None

    @pytest.mark.parametrize("value", [None, ""])
    @pytest.mark.asyncio
    async def test_missing_payload_returns_none(self, preferences, value):
        user = _user()
        if value is not None:
            preferences.values[_prefs_key(user)] = value
        source = CapacitorLegacyConfigSource()
        await source.connect(user)

        assert await source.load() is None

    @pytest.mark.asyncio
    async def test_bridge_failure_returns_none(self, preferences):
        user = _user()
        preferences.values[_prefs_key(user)] = read_sample("mobile_v8_custom.json")
        preferences.error = RuntimeError("bridge unavailable")
        source = CapacitorLegacyConfigSource()
        await source.connect(user)

        assert await source.load() is None

    @pytest.mark.asyncio
    async def test_reads_only_connected_user_payload(self, preferences):
        user = _user()
        preferences.values[_prefs_key(_user())] = read_sample("mobile_v8_custom.json")
        source = CapacitorLegacyConfigSource()
        await source.connect(user)

        assert await source.load() is None

    @pytest.mark.asyncio
    async def test_not_connected_returns_none(self, preferences):
        user = _user()
        preferences.values[_prefs_key(user)] = read_sample("mobile_v8_custom.json")
        source = CapacitorLegacyConfigSource()
        await source.connect(user)
        await source.disconnect()

        assert await source.load() is None
        assert await CapacitorLegacyConfigSource().load() is None


class TestMobileSettingsMigration:
    @pytest.mark.parametrize("sample", MOBILE_SAMPLES, ids=str)
    @pytest.mark.asyncio
    async def test_migrates_preferences_config(self, preferences, sample):
        user = _user()
        preferences.values[_prefs_key(user)] = read_sample(sample.name)
        client, conn = _client()
        repository = SettingsRepository(client, CapacitorLegacyConfigSource())
        await repository.connect(user)

        await _migrate(client, repository)

        rows = {row["key"] for row in conn.execute('SELECT "key" FROM settings')}
        assert rows == sample.sections
        assert_same_settings(await repository.load(), sample.expected())
        assert preferences.values[_prefs_key(user)] == read_sample(sample.name)
        conn.close()

    @pytest.mark.parametrize("name", BROKEN_MOBILE_SAMPLES)
    @pytest.mark.asyncio
    async def test_broken_preferences_config_is_ignored(self, preferences, name):
        user = _user()
        preferences.values[_prefs_key(user)] = read_sample(name)
        client, conn = _client()
        repository = SettingsRepository(client, CapacitorLegacyConfigSource())
        await repository.connect(user)

        await _migrate(client, repository)

        assert conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0
        assert_same_settings(await repository.load(), default_settings())
        conn.close()

    @pytest.mark.asyncio
    async def test_bridge_failure_does_not_raise(self, preferences):
        user = _user()
        preferences.error = RuntimeError("bridge unavailable")
        client, conn = _client()
        repository = SettingsRepository(client, CapacitorLegacyConfigSource())
        await repository.connect(user)

        await _migrate(client, repository)

        assert conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0
        conn.close()


class TestCapacitorLegacyConfigBackupImporter:
    @pytest.mark.asyncio
    async def test_imports_staged_mobile_backup(self, backup_plugin, repository):
        backup_plugin.files[DECOMPILED_CONFIG] = mobile_backup_payload(
            "mobile_v8_custom.json"
        )

        await CapacitorLegacyConfigBackupImporter(repository).import_data(b"")

        assert_same_settings(await repository.load(), custom_settings())
        assert (await repository.load()).lastUpdate == V8_LAST_UPDATE.isoformat()
        assert backup_plugin.deleted == [DECOMPILED_CONFIG]
        assert DECOMPILED_CONFIG not in backup_plugin.files

    @pytest.mark.asyncio
    async def test_imports_staged_desktop_backup(self, backup_plugin, repository):
        backup_plugin.files[DECOMPILED_CONFIG] = read_sample(
            "desktop_v8_labeling.yml"
        ).encode()

        await CapacitorLegacyConfigBackupImporter(repository).import_data(b"")

        assert_same_settings(await repository.load(), labeling_settings())

    @pytest.mark.asyncio
    async def test_ignores_payload_argument(self, backup_plugin, repository):
        backup_plugin.files[DECOMPILED_CONFIG] = mobile_backup_payload(
            "mobile_v8_custom.json"
        )

        await CapacitorLegacyConfigBackupImporter(repository).import_data(
            read_sample("desktop_v8_labeling.yml").encode()
        )

        assert_same_settings(await repository.load(), custom_settings())

    @pytest.mark.asyncio
    async def test_deletes_staging_file_when_read_fails(
        self, backup_plugin, repository
    ):
        with pytest.raises(RuntimeError):
            await CapacitorLegacyConfigBackupImporter(repository).import_data(b"")

        assert backup_plugin.deleted == [DECOMPILED_CONFIG]
        assert_same_settings(await repository.load(), default_settings())

    @pytest.mark.asyncio
    async def test_deletes_staging_file_when_payload_is_invalid(
        self, backup_plugin, repository
    ):
        backup_plugin.files[DECOMPILED_CONFIG] = b"- a\n- b\n"

        with pytest.raises(ValueError):
            await CapacitorLegacyConfigBackupImporter(repository).import_data(b"")

        assert backup_plugin.deleted == [DECOMPILED_CONFIG]
        assert_same_settings(await repository.load(), default_settings())
