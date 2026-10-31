import pytest

from domain.settings import Settings
from infrastructure.repository.db import manager as manager_module
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.settings.settings_mapper import parse_section
from tests.legacy_config_samples import (
    SECTION_KEYS,
    assert_same_settings,
    custom_settings,
    default_settings,
    read_sample,
)

SIGNUP_URL = "/api/v1/signup"
LOGIN_URL = "/api/v1/login"
LOGOUT_URL = "/api/v1/logout"
CHANGE_PASSWORD_URL = "/api/v1/change-password"
SETTINGS_URL = "/api/v1/settings"

USERNAME = "testuser"
PASSWORD = "securePass123"
NEW_PASSWORD = "newPass456!"

PRE_SETTINGS_VERSIONS = versions[
    : [v.name for v in versions].index("v0.11.0:4_settings")
]


async def _signup_legacy_user(client, monkeypatch, tmp_path, config_sample=None):
    with monkeypatch.context() as patch:
        patch.setattr(manager_module, "versions", PRE_SETTINGS_VERSIONS)
        response = await client.post(
            SIGNUP_URL, json={"username": USERNAME, "password": PASSWORD}
        )
        assert response.status_code == 204
        response = await client.post(LOGOUT_URL)
        assert response.status_code == 204
    user_path = next(tmp_path.rglob("data.db")).parent
    if config_sample:
        (user_path / "config.yml").write_text(read_sample(config_sample))
    return user_path


async def _login(client, password=PASSWORD):
    response = await client.post(
        LOGIN_URL, json={"username": USERNAME, "password": password}
    )
    assert response.status_code == 204


async def _get_settings(client):
    response = await client.get(SETTINGS_URL)
    assert response.status_code == 200
    body = await response.get_json()
    return Settings(
        lastUpdate=body["lastUpdate"],
        version=body["version"],
        **{key: parse_section(key, body[key]) for key in SECTION_KEYS},
    )


class TestSettingsMigrationFlow:
    @pytest.mark.asyncio
    async def test_login_migrates_legacy_config(self, client, monkeypatch, tmp_path):
        user_path = await _signup_legacy_user(
            client, monkeypatch, tmp_path, "desktop_v8_custom.yml"
        )

        await _login(client)

        assert_same_settings(await _get_settings(client), custom_settings())
        assert (user_path / "config.yml").read_text() == read_sample(
            "desktop_v8_custom.yml"
        )

    @pytest.mark.asyncio
    async def test_updated_settings_are_stored_in_db_only(
        self, client, monkeypatch, tmp_path
    ):
        user_path = await _signup_legacy_user(
            client, monkeypatch, tmp_path, "desktop_v8_default.yml"
        )
        await _login(client)
        settings = await (await client.get(SETTINGS_URL)).get_json()
        settings["general"]["defaultCurrency"] = "USD"

        response = await client.post(SETTINGS_URL, json=settings)
        assert response.status_code == 204
        await client.post(LOGOUT_URL)
        await _login(client)

        assert (await _get_settings(client)).general.defaultCurrency == "USD"
        assert (user_path / "config.yml").read_text() == read_sample(
            "desktop_v8_default.yml"
        )

    @pytest.mark.asyncio
    async def test_legacy_user_without_config_gets_defaults(
        self, client, monkeypatch, tmp_path
    ):
        user_path = await _signup_legacy_user(client, monkeypatch, tmp_path)

        await _login(client)

        assert_same_settings(await _get_settings(client), default_settings())
        assert not (user_path / "config.yml").exists()

    @pytest.mark.asyncio
    async def test_broken_legacy_config_does_not_block_login(
        self, client, monkeypatch, tmp_path
    ):
        await _signup_legacy_user(
            client, monkeypatch, tmp_path, "desktop_invalid_yaml.yml"
        )

        await _login(client)

        assert_same_settings(await _get_settings(client), default_settings())

    @pytest.mark.asyncio
    async def test_change_password_migrates_legacy_config(
        self, client, monkeypatch, tmp_path
    ):
        user_path = await _signup_legacy_user(
            client, monkeypatch, tmp_path, "desktop_v8_custom.yml"
        )

        response = await client.post(
            CHANGE_PASSWORD_URL,
            json={
                "username": USERNAME,
                "oldPassword": PASSWORD,
                "newPassword": NEW_PASSWORD,
            },
        )
        assert response.status_code == 204
        (user_path / "config.yml").unlink()
        await _login(client, NEW_PASSWORD)

        assert_same_settings(await _get_settings(client), custom_settings())

    @pytest.mark.asyncio
    async def test_fresh_signup_does_not_create_config_file(self, client, tmp_path):
        response = await client.post(
            SIGNUP_URL, json={"username": USERNAME, "password": PASSWORD}
        )
        assert response.status_code == 204

        assert_same_settings(await _get_settings(client), default_settings())
        assert not list(tmp_path.rglob("config.yml"))
