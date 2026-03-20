from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import uuid4

import pytest

from domain.exception.exceptions import NoUserLogged
from domain.settings import CURRENT_VERSION, AssetConfig, CryptoAssetConfig, Settings
from domain.user import User
from infrastructure.config.config_loader import ConfigLoader


class _TestEnum(Enum):
    VALUE_A = "a"
    VALUE_B = "b"


def _make_user(tmp_path: Path) -> User:
    return User(id=uuid4(), username="testuser", path=tmp_path, last_login=None)


def _make_settings(last_update: str = "2024-01-01T00:00:00+00:00") -> Settings:
    return Settings(
        lastUpdate=last_update,
        assets=AssetConfig(crypto=CryptoAssetConfig()),
    )


class TestCheckConnected:
    def test_raises_no_user_logged_when_not_connected(self):
        loader = ConfigLoader()

        with pytest.raises(NoUserLogged):
            loader._check_connected()


class TestConnect:
    @pytest.mark.asyncio
    async def test_creates_default_config_when_file_missing(self, tmp_path):
        user = _make_user(tmp_path)
        loader = ConfigLoader()

        await loader.connect(user)

        assert (tmp_path / "config.yml").is_file()

    @pytest.mark.asyncio
    async def test_populates_cache_after_connect(self, tmp_path):
        user = _make_user(tmp_path)
        loader = ConfigLoader()

        await loader.connect(user)

        assert loader._cache is not None
        assert isinstance(loader._cache, Settings)


class TestLoad:
    @pytest.mark.asyncio
    async def test_returns_cached_settings_on_second_call(self, tmp_path):
        user = _make_user(tmp_path)
        loader = ConfigLoader()
        await loader.connect(user)

        first = await loader.load()
        second = await loader.load()

        assert first is second


class TestSave:
    @pytest.mark.asyncio
    async def test_writes_config_and_updates_cache(self, tmp_path):
        user = _make_user(tmp_path)
        loader = ConfigLoader()
        await loader.connect(user)

        new_settings = _make_settings()
        await loader.save(new_settings)

        assert loader._cache is new_settings
        content = (tmp_path / "config.yml").read_text()
        assert str(CURRENT_VERSION) in content

    @pytest.mark.asyncio
    async def test_updates_last_update_timestamp(self, tmp_path):
        user = _make_user(tmp_path)
        loader = ConfigLoader()
        await loader.connect(user)

        settings = _make_settings("2020-01-01T00:00:00")
        await loader.save(settings)

        assert settings.lastUpdate != "2020-01-01T00:00:00"


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_clears_config_file_and_cache(self, tmp_path):
        user = _make_user(tmp_path)
        loader = ConfigLoader()
        await loader.connect(user)

        await loader.disconnect()

        assert loader._config_file is None
        assert loader._cache is None

    @pytest.mark.asyncio
    async def test_load_raises_after_disconnect(self, tmp_path):
        user = _make_user(tmp_path)
        loader = ConfigLoader()
        await loader.connect(user)
        await loader.disconnect()

        with pytest.raises(NoUserLogged):
            await loader.load()


class TestExport:
    @pytest.mark.asyncio
    async def test_returns_file_contents_as_bytes(self, tmp_path):
        user = _make_user(tmp_path)
        loader = ConfigLoader()
        await loader.connect(user)

        result = await loader.export()

        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result == (tmp_path / "config.yml").read_bytes()


class TestImportData:
    @pytest.mark.asyncio
    async def test_writes_bytes_and_clears_cache(self, tmp_path):
        user = _make_user(tmp_path)
        loader = ConfigLoader()
        await loader.connect(user)

        payload = b"lastUpdate: '2024-06-01'\nversion: '6'\n"
        await loader.import_data(payload)

        assert (tmp_path / "config.yml").read_bytes() == payload
        assert loader._cache is None


class TestToYamlSafe:
    def test_converts_enum_to_value(self):
        result = ConfigLoader._to_yaml_safe(_TestEnum.VALUE_A)

        assert result == "a"

    def test_converts_datetime_to_isoformat(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)

        result = ConfigLoader._to_yaml_safe(dt)

        assert result == "2024-01-15T10:30:00"

    def test_converts_list_with_mixed_types(self):
        data = [_TestEnum.VALUE_B, datetime(2024, 6, 1), "plain"]

        result = ConfigLoader._to_yaml_safe(data)

        assert result == ["b", "2024-06-01T00:00:00", "plain"]

    def test_converts_dict_recursively(self):
        data = {
            "status": _TestEnum.VALUE_A,
            "nested": {"ts": datetime(2024, 3, 1, 8, 0)},
        }

        result = ConfigLoader._to_yaml_safe(data)

        assert result["status"] == "a"
        assert result["nested"]["ts"] == "2024-03-01T08:00:00"

    def test_returns_plain_values_unchanged(self):
        assert ConfigLoader._to_yaml_safe("hello") == "hello"
        assert ConfigLoader._to_yaml_safe(42) == 42
        assert ConfigLoader._to_yaml_safe(None) is None
