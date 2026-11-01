import json
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from domain.settings import (
    CURRENT_VERSION,
    GeneralConfig,
    LabelingConfig,
    PartialSettings,
    SettingsSection,
)
from infrastructure.config.base_config import BASE_CONFIG
from infrastructure.config.legacy_config_backup_importer import (
    LegacyConfigBackupImporter,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v11.v0110_4_settings import (
    V01104Settings,
)
from infrastructure.repository.settings.settings_mapper import settings_to_sections
from infrastructure.repository.settings.settings_repository import SettingsRepository
from tests.legacy_config_samples import (
    assert_same_settings,
    custom_settings,
    default_settings,
    labeling_settings,
    mobile_backup_payload,
    read_sample,
)

OLD_TS = "2020-01-01T00:00:00+00:00"
SENTINEL_LAST_UPDATE = "2000-01-01T00:00:00+00:00"


@pytest_asyncio.fixture
async def setup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "INSERT INTO sys_config (key, value) VALUES ('last_update', ?)",
        (SENTINEL_LAST_UPDATE,),
    )
    conn.commit()
    db_client = DBClient(conn)
    async with db_client.tx(skip_last_update=True) as cursor:
        await V01104Settings().upgrade(cursor, DatasourceInitContext(config=None))
    legacy_source = MagicMock()
    legacy_source.connect = AsyncMock()
    legacy_source.disconnect = AsyncMock()
    legacy_source.load = AsyncMock(return_value=None)
    repository = SettingsRepository(db_client, legacy_source)
    yield repository, conn, legacy_source
    conn.close()


def _rows(conn) -> dict[str, tuple[dict, str]]:
    return {
        row["key"]: (json.loads(row["value"]), row["updated_at"])
        for row in conn.execute('SELECT "key", value, updated_at FROM settings')
    }


def _insert(conn, key, value, updated_at):
    conn.execute(
        'INSERT INTO settings ("key", value, updated_at) VALUES (?, ?, ?)',
        (key, value, updated_at),
    )
    conn.commit()


def _sys_last_update(conn) -> str:
    return conn.execute(
        "SELECT value FROM sys_config WHERE key = 'last_update'"
    ).fetchone()[0]


class TestLoad:
    @pytest.mark.asyncio
    async def test_returns_defaults_when_empty(self, setup):
        repository, *_ = setup

        settings = await repository.load()

        assert_same_settings(settings, default_settings())
        assert settings.lastUpdate == BASE_CONFIG.lastUpdate
        assert settings.version == CURRENT_VERSION

    @pytest.mark.asyncio
    async def test_last_update_is_latest_row_timestamp(self, setup):
        repository, conn, _ = setup
        sections = settings_to_sections(custom_settings())
        _insert(conn, "general", json.dumps(sections["general"]), OLD_TS)
        _insert(
            conn, "assets", json.dumps(sections["assets"]), "2026-03-01T10:00:00+01:00"
        )

        settings = await repository.load()

        assert datetime.fromisoformat(settings.lastUpdate) == datetime.fromisoformat(
            "2026-03-01T10:00:00+01:00"
        )
        assert settings.general == custom_settings().general
        assert settings.assets == custom_settings().assets
        assert settings.data == default_settings().data

    @pytest.mark.asyncio
    async def test_invalid_json_row_falls_back_to_default(self, setup):
        repository, conn, _ = setup
        sections = settings_to_sections(custom_settings())
        _insert(conn, "general", "{not json", OLD_TS)
        _insert(conn, "assets", json.dumps(sections["assets"]), OLD_TS)

        settings = await repository.load()

        assert settings.general == default_settings().general
        assert settings.assets == custom_settings().assets

    @pytest.mark.asyncio
    async def test_invalid_section_row_falls_back_to_default(self, setup):
        repository, conn, _ = setup
        _insert(conn, "general", json.dumps({"editMode": "BOGUS"}), OLD_TS)
        _insert(conn, "data", json.dumps([1, 2]), OLD_TS)

        settings = await repository.load()

        assert_same_settings(settings, default_settings())

    @pytest.mark.asyncio
    async def test_unknown_rows_are_ignored(self, setup):
        repository, conn, _ = setup
        _insert(conn, "future", json.dumps({"a": 1}), OLD_TS)

        settings = await repository.load()

        assert_same_settings(settings, default_settings())


class TestLoadSections:
    @pytest.mark.asyncio
    async def test_returns_only_requested_sections(self, setup):
        repository, conn, _ = setup
        await repository.save(custom_settings())

        partial = await repository.load_sections(
            {SettingsSection.GENERAL, SettingsSection.ASSETS}
        )

        assert partial.included_sections() == [
            SettingsSection.GENERAL,
            SettingsSection.ASSETS,
        ]
        assert partial.general == custom_settings().general
        assert partial.assets == custom_settings().assets
        assert partial.data is None
        assert partial.labeling is None
        assert partial.version == CURRENT_VERSION

    @pytest.mark.asyncio
    async def test_missing_rows_fall_back_to_defaults(self, setup):
        repository, *_ = setup

        partial = await repository.load_sections(
            {SettingsSection.ASSETS, SettingsSection.LABELING}
        )

        assert partial.assets == default_settings().assets
        assert partial.labeling == default_settings().labeling
        assert partial.lastUpdate == BASE_CONFIG.lastUpdate

    @pytest.mark.asyncio
    async def test_invalid_row_falls_back_to_default(self, setup):
        repository, conn, _ = setup
        _insert(conn, "general", "{not json", OLD_TS)

        partial = await repository.load_sections({SettingsSection.GENERAL})

        assert partial.general == default_settings().general

    @pytest.mark.asyncio
    async def test_last_update_only_considers_requested_rows(self, setup):
        repository, conn, _ = setup
        sections = settings_to_sections(custom_settings())
        _insert(conn, "general", json.dumps(sections["general"]), OLD_TS)
        _insert(
            conn, "assets", json.dumps(sections["assets"]), "2026-03-01T10:00:00+01:00"
        )

        partial = await repository.load_sections({SettingsSection.GENERAL})

        assert datetime.fromisoformat(partial.lastUpdate) == datetime.fromisoformat(
            OLD_TS
        )

    @pytest.mark.asyncio
    async def test_empty_request_returns_no_sections(self, setup):
        repository, *_ = setup

        partial = await repository.load_sections(set())

        assert partial.included_sections() == []

    @pytest.mark.asyncio
    async def test_round_trip(self, setup):
        repository, conn, _ = setup

        await repository.save(custom_settings())
        settings = await repository.load()

        assert_same_settings(settings, custom_settings())
        assert set(_rows(conn)) == {
            "general",
            "data",
            "export",
            "importing",
            "assets",
            "labeling",
        }

    @pytest.mark.asyncio
    async def test_ignores_incoming_last_update(self, setup):
        repository, conn, _ = setup
        settings = custom_settings()
        settings.lastUpdate = OLD_TS

        before = datetime.now().astimezone()
        await repository.save(settings)

        for _, updated_at in _rows(conn).values():
            assert datetime.fromisoformat(updated_at) >= before

    @pytest.mark.asyncio
    async def test_only_changed_sections_are_written(self, setup):
        repository, conn, _ = setup
        await repository.save(default_settings())
        conn.execute("UPDATE settings SET updated_at = ?", (OLD_TS,))
        conn.commit()

        settings = default_settings()
        settings.general.defaultCurrency = "USD"
        await repository.save(settings)

        rows = _rows(conn)
        assert rows["general"][0]["defaultCurrency"] == "USD"
        assert rows["general"][1] != OLD_TS
        assert {k for k, (_, ts) in rows.items() if ts == OLD_TS} == {
            "data",
            "export",
            "importing",
            "assets",
            "labeling",
        }

    @pytest.mark.asyncio
    async def test_marks_data_as_modified(self, setup):
        repository, conn, _ = setup

        await repository.save(custom_settings())

        assert _sys_last_update(conn) != SENTINEL_LAST_UPDATE

    @pytest.mark.asyncio
    async def test_no_changes_is_a_noop(self, setup):
        repository, conn, _ = setup
        await repository.save(custom_settings())
        conn.execute("UPDATE settings SET updated_at = ?", (OLD_TS,))
        conn.execute(
            "UPDATE sys_config SET value = ? WHERE key = 'last_update'",
            (SENTINEL_LAST_UPDATE,),
        )
        conn.commit()

        await repository.save(await repository.load())

        assert all(ts == OLD_TS for _, ts in _rows(conn).values())
        assert _sys_last_update(conn) == SENTINEL_LAST_UPDATE

    @pytest.mark.asyncio
    async def test_overwrites_invalid_stored_row(self, setup):
        repository, conn, _ = setup
        _insert(conn, "general", "{not json", OLD_TS)

        await repository.save(custom_settings())

        assert _rows(conn)["general"][0]["defaultCurrency"] == "USD"


class TestSavePartial:
    @pytest.mark.asyncio
    async def test_only_provided_sections_are_written(self, setup):
        repository, conn, _ = setup
        await repository.save(custom_settings())
        conn.execute("UPDATE settings SET updated_at = ?", (OLD_TS,))
        conn.commit()

        await repository.save(PartialSettings(labeling=labeling_settings().labeling))

        rows = _rows(conn)
        assert rows["labeling"][1] != OLD_TS
        assert {k for k, (_, ts) in rows.items() if ts == OLD_TS} == {
            "general",
            "data",
            "export",
            "importing",
            "assets",
        }
        settings = await repository.load()
        assert settings.labeling == labeling_settings().labeling
        assert settings.general == custom_settings().general
        assert settings.assets == custom_settings().assets

    @pytest.mark.asyncio
    async def test_creates_only_provided_rows_on_empty_table(self, setup):
        repository, conn, _ = setup

        await repository.save(
            PartialSettings(general=GeneralConfig(defaultCurrency="USD"))
        )

        assert set(_rows(conn)) == {"general"}
        settings = await repository.load()
        assert settings.general.defaultCurrency == "USD"
        assert settings.assets == default_settings().assets

    @pytest.mark.asyncio
    async def test_unchanged_partial_is_a_noop(self, setup):
        repository, conn, _ = setup
        await repository.save(custom_settings())
        conn.execute("UPDATE settings SET updated_at = ?", (OLD_TS,))
        conn.execute(
            "UPDATE sys_config SET value = ? WHERE key = 'last_update'",
            (SENTINEL_LAST_UPDATE,),
        )
        conn.commit()

        await repository.save(
            await repository.load_sections(
                {SettingsSection.GENERAL, SettingsSection.EXPORT}
            )
        )

        assert all(ts == OLD_TS for _, ts in _rows(conn).values())
        assert _sys_last_update(conn) == SENTINEL_LAST_UPDATE

    @pytest.mark.asyncio
    async def test_empty_partial_is_a_noop(self, setup):
        repository, conn, _ = setup

        await repository.save(PartialSettings())

        assert _rows(conn) == {}
        assert _sys_last_update(conn) == SENTINEL_LAST_UPDATE

    @pytest.mark.asyncio
    async def test_default_section_resets_stored_values(self, setup):
        repository, conn, _ = setup
        await repository.save(labeling_settings())

        await repository.save(PartialSettings(labeling=LabelingConfig()))

        settings = await repository.load()
        assert settings.labeling == LabelingConfig()


class TestApplyLegacy:
    @pytest.mark.asyncio
    async def test_empty_sections_are_not_applied(self, setup):
        repository, conn, _ = setup

        applied = await repository.apply_legacy({}, datetime.now().astimezone())

        assert applied is False
        assert _rows(conn) == {}

    @pytest.mark.asyncio
    async def test_applies_on_empty_table_with_legacy_timestamp(self, setup):
        repository, conn, _ = setup
        sections = settings_to_sections(labeling_settings())
        last_update = datetime.fromisoformat("2026-03-01T10:00:00+01:00")

        applied = await repository.apply_legacy(sections, last_update)

        assert applied is True
        rows = _rows(conn)
        assert {k: v for k, (v, _) in rows.items()} == sections
        assert {datetime.fromisoformat(ts) for _, ts in rows.values()} == {last_update}
        assert_same_settings(await repository.load(), labeling_settings())

    @pytest.mark.asyncio
    async def test_applies_on_empty_table_without_timestamp(self, setup):
        repository, conn, _ = setup
        sections = settings_to_sections(labeling_settings())

        before = datetime.now().astimezone()
        applied = await repository.apply_legacy(sections, None)

        assert applied is True
        for _, ts in _rows(conn).values():
            assert datetime.fromisoformat(ts) >= before

    @pytest.mark.asyncio
    async def test_newer_legacy_replaces_all_rows(self, setup):
        repository, conn, _ = setup
        await repository.save(custom_settings())
        conn.execute("UPDATE settings SET updated_at = ?", (OLD_TS,))
        conn.commit()
        sections = settings_to_sections(labeling_settings())
        del sections["export"]

        applied = await repository.apply_legacy(sections, datetime.now().astimezone())

        assert applied is True
        assert "export" not in _rows(conn)
        assert_same_settings(await repository.load(), labeling_settings())

    @pytest.mark.parametrize("delta", [timedelta(0), timedelta(seconds=-1)])
    @pytest.mark.asyncio
    async def test_older_or_equal_legacy_is_skipped(self, setup, delta):
        repository, conn, _ = setup
        await repository.save(custom_settings())
        current = max(datetime.fromisoformat(ts) for _, ts in _rows(conn).values())

        applied = await repository.apply_legacy(
            settings_to_sections(labeling_settings()), current + delta
        )

        assert applied is False
        assert_same_settings(await repository.load(), custom_settings())

    @pytest.mark.asyncio
    async def test_legacy_without_timestamp_is_skipped_when_rows_exist(self, setup):
        repository, *_ = setup
        await repository.save(custom_settings())

        applied = await repository.apply_legacy(
            settings_to_sections(labeling_settings()), None
        )

        assert applied is False
        assert_same_settings(await repository.load(), custom_settings())

    @pytest.mark.asyncio
    async def test_is_idempotent(self, setup):
        repository, *_ = setup
        sections = settings_to_sections(labeling_settings())
        last_update = datetime.fromisoformat("2026-03-01T10:00:00+01:00")

        assert await repository.apply_legacy(sections, last_update) is True
        assert await repository.apply_legacy(sections, last_update) is False


class TestLegacySource:
    @pytest.mark.asyncio
    async def test_connect_and_disconnect_delegate(self, setup):
        repository, _, legacy_source = setup
        user = MagicMock()

        await repository.connect(user)
        await repository.disconnect()

        legacy_source.connect.assert_awaited_once_with(user)
        legacy_source.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_load_legacy_returns_source_data(self, setup):
        repository, _, legacy_source = setup
        legacy_source.load.return_value = {"general": {}}

        assert await repository.load_legacy() == {"general": {}}

    @pytest.mark.asyncio
    async def test_load_legacy_swallows_errors(self, setup):
        repository, _, legacy_source = setup
        legacy_source.load.side_effect = RuntimeError("boom")

        assert await repository.load_legacy() is None


class TestLegacyConfigBackupImporter:
    @pytest.mark.asyncio
    async def test_imports_desktop_backup_payload(self, setup):
        repository, *_ = setup
        importer = LegacyConfigBackupImporter(repository)

        await importer.import_data(read_sample("desktop_v8_custom.yml").encode())

        assert_same_settings(await repository.load(), custom_settings())

    @pytest.mark.asyncio
    async def test_imports_mobile_backup_payload(self, setup):
        repository, *_ = setup
        importer = LegacyConfigBackupImporter(repository)

        await importer.import_data(mobile_backup_payload("mobile_v8_labeling.json"))

        assert_same_settings(await repository.load(), labeling_settings())

    @pytest.mark.asyncio
    async def test_skips_older_backup_payload(self, setup):
        repository, *_ = setup
        await repository.save(labeling_settings())
        importer = LegacyConfigBackupImporter(repository)

        await importer.import_data(read_sample("desktop_v8_custom.yml").encode())

        assert_same_settings(await repository.load(), labeling_settings())

    @pytest.mark.parametrize(
        "payload", [b"- general\n- data\n", b"just a string\n", b""]
    )
    @pytest.mark.asyncio
    async def test_rejects_non_mapping_payload(self, setup, payload):
        repository, conn, _ = setup
        importer = LegacyConfigBackupImporter(repository)

        with pytest.raises(ValueError):
            await importer.import_data(payload)

        assert _rows(conn) == {}

    @pytest.mark.asyncio
    async def test_rejects_invalid_yaml(self, setup):
        repository, conn, _ = setup
        importer = LegacyConfigBackupImporter(repository)

        with pytest.raises(Exception):
            await importer.import_data(read_sample("desktop_invalid_yaml.yml").encode())

        assert _rows(conn) == {}
