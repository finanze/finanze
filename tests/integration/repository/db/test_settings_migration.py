import ast
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.config.file_legacy_config_source import FileLegacyConfigSource
from infrastructure.repository.db import settings_snapshot
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.db.versions.v0.v11 import v0110_4_settings
from infrastructure.repository.db.versions.v0.v11.v0110_4_settings import (
    V01104Settings,
)
from infrastructure.repository.settings.settings_repository import SettingsRepository
from tests.legacy_config_samples import (
    BROKEN_DESKTOP_SAMPLES,
    DESKTOP_SAMPLES,
    assert_last_update,
    assert_same_settings,
    default_settings,
    read_sample,
)

SETTINGS_MIGRATION = "v0.11.0:4_settings"

CORE_IMPORT_PREFIXES = (
    "domain.data_init",
    "infrastructure.repository.db.",
)


@pytest_asyncio.fixture
async def setup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    yield DBClient(conn), conn
    conn.close()


async def _run_migration(db_client, config_port):
    async with db_client.tx(skip_last_update=True) as cursor:
        await V01104Settings().upgrade(
            cursor, DatasourceInitContext(config=config_port)
        )


def _rows(conn):
    return {
        row["key"]: (json.loads(row["value"]), row["updated_at"])
        for row in conn.execute('SELECT "key", value, updated_at FROM settings')
    }


def _is_core_import(module: str) -> bool:
    return module.split(".")[0] in sys.stdlib_module_names or module.startswith(
        CORE_IMPORT_PREFIXES
    )


async def _connected_repository(db_client, tmp_path) -> SettingsRepository:
    repository = SettingsRepository(db_client, FileLegacyConfigSource())
    await repository.connect(MagicMock(path=tmp_path))
    return repository


class TestSettingsMigration:
    @pytest.mark.asyncio
    async def test_creates_table_without_context(self, setup):
        db_client, conn = setup

        await _run_migration(db_client, None)

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(settings)")}
        assert columns == {"key", "value", "updated_at"}
        assert _rows(conn) == {}

    @pytest.mark.asyncio
    async def test_creates_empty_table_when_no_legacy_file(self, setup, tmp_path):
        db_client, conn = setup
        repository = await _connected_repository(db_client, tmp_path)

        await _run_migration(db_client, repository)

        assert _rows(conn) == {}
        assert_same_settings(await repository.load(), default_settings())
        assert not (tmp_path / "config.yml").exists()

    @pytest.mark.parametrize("sample", DESKTOP_SAMPLES, ids=str)
    @pytest.mark.asyncio
    async def test_migrates_desktop_config(self, setup, tmp_path, sample):
        db_client, conn = setup
        content = read_sample(sample.name)
        (tmp_path / "config.yml").write_text(content)
        repository = await _connected_repository(db_client, tmp_path)

        before = datetime.now().astimezone()
        await _run_migration(db_client, repository)
        after = datetime.now().astimezone()

        rows = _rows(conn)
        assert set(rows) == sample.sections
        timestamps = {datetime.fromisoformat(ts) for _, ts in rows.values()}
        assert len(timestamps) == 1
        assert_last_update(timestamps.pop(), sample.last_update, before, after)
        assert_same_settings(await repository.load(), sample.expected())
        assert (tmp_path / "config.yml").read_text() == content

    @pytest.mark.parametrize("name", BROKEN_DESKTOP_SAMPLES)
    @pytest.mark.asyncio
    async def test_broken_desktop_config_is_ignored(self, setup, tmp_path, name):
        db_client, conn = setup
        (tmp_path / "config.yml").write_text(read_sample(name))
        repository = await _connected_repository(db_client, tmp_path)

        await _run_migration(db_client, repository)

        assert _rows(conn) == {}
        assert_same_settings(await repository.load(), default_settings())

    @pytest.mark.asyncio
    async def test_failing_config_port_does_not_raise(self, setup):
        db_client, conn = setup
        config_port = MagicMock()
        config_port.load_legacy = AsyncMock(side_effect=RuntimeError("boom"))

        await _run_migration(db_client, config_port)

        assert _rows(conn) == {}

    @pytest.mark.parametrize("value", [None, [], "text", AsyncMock()])
    @pytest.mark.asyncio
    async def test_unexpected_legacy_values_are_ignored(self, setup, value):
        db_client, conn = setup
        config_port = MagicMock()
        config_port.load_legacy = AsyncMock(return_value=value)

        await _run_migration(db_client, config_port)

        assert _rows(conn) == {}


class TestSettingsMigrationGuards:
    def test_registered_once_with_stable_name(self):
        names = [v.name for v in versions]

        assert names.count(SETTINGS_MIGRATION) == 1
        assert isinstance(versions[names.index(SETTINGS_MIGRATION)], V01104Settings)

    def test_runs_after_previous_v0110_migrations(self):
        names = [v.name for v in versions]
        index = names.index(SETTINGS_MIGRATION)

        assert names[index - 1] == "v0.11.0:3_periodic_flow_budget_label"

    @pytest.mark.parametrize("module", [v0110_4_settings, settings_snapshot])
    def test_core_tier_modules_only_import_core_modules_at_top_level(self, module):
        tree = ast.parse(Path(module.__file__).read_text())

        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and _is_core_import(node.module), node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert _is_core_import(alias.name), alias.name
