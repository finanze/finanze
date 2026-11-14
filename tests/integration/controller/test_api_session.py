from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from application.ports.cloud_register import CloudRegister
from application.ports.feature_flag_port import FeatureFlagPort
from application.ports.server_details_port import ServerDetailsPort
from application.ports.sheets_initiator import SheetsInitiator
from application.use_cases.authorize_api_access import AuthorizeApiAccessImpl
from application.use_cases.get_settings import GetSettingsImpl
from application.use_cases.get_status import GetStatusImpl
from application.use_cases.register_user import RegisterUserImpl
from application.use_cases.user_login import UserLoginImpl
from application.use_cases.user_logout import UserLogoutImpl
from domain.platform import OS
from domain.status import BackendDetails, BackendOptions
from domain.user_login import LoginRequest
from infrastructure.api_session.in_memory_api_session_store import (
    InMemoryApiSessionStore,
)
from infrastructure.config.file_legacy_config_source import FileLegacyConfigSource
from infrastructure.controller.api_session_guard import register_api_session_guard
from infrastructure.controller.config import quart
from infrastructure.controller.routes.get_settings import get_settings
from infrastructure.controller.routes.get_status import status
from infrastructure.controller.routes.logout import logout
from infrastructure.controller.routes.register_user import register_user
from infrastructure.controller.routes.user_login import user_login
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.manager import DBManager
from infrastructure.repository.settings.settings_repository import SettingsRepository
from infrastructure.user_files.user_data_manager import UserDataManager

USERNAME = "testuser"
PASSWORD = "securePass123"
PING_URL = "/api/v1/ping"
SETTINGS_URL = "/api/v1/settings"
STATUS_URL = "/api/v1/status"


@pytest_asyncio.fixture
async def env(tmp_path):
    db_client = DBClient()
    db_manager = DBManager(db_client)
    data_manager = UserDataManager(str(tmp_path))
    settings_repository = SettingsRepository(db_client, FileLegacyConfigSource())
    sheets_initiator = MagicMock(spec=SheetsInitiator)
    cloud_register = MagicMock(spec=CloudRegister)
    cloud_register.connect = AsyncMock()
    cloud_register.disconnect = AsyncMock()

    server_details_port = MagicMock(spec=ServerDetailsPort)
    server_details_port.get_backend_details = AsyncMock(
        return_value=BackendDetails(
            version="0.0.0-test", platform_type=OS.MACOS, options=BackendOptions()
        )
    )
    feature_flag_port = MagicMock(spec=FeatureFlagPort)
    feature_flag_port.get_all.return_value = {}

    api_session_port = InMemoryApiSessionStore()
    common = (db_manager, data_manager, settings_repository, sheets_initiator)
    register_user_uc = RegisterUserImpl(
        *common, cloud_register, api_session_port=api_session_port
    )
    user_login_uc = UserLoginImpl(
        *common, cloud_register, api_session_port=api_session_port
    )
    user_logout_uc = UserLogoutImpl(
        db_manager,
        settings_repository,
        sheets_initiator,
        cloud_register,
        api_session_port=api_session_port,
    )
    get_status_uc = GetStatusImpl(
        db_manager,
        data_manager,
        server_details_port,
        feature_flag_port,
        api_session_port=api_session_port,
    )
    get_settings_uc = GetSettingsImpl(settings_repository)

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "logo.png").write_bytes(b"png")
    app = quart(static_dir)
    register_api_session_guard(
        app, AuthorizeApiAccessImpl(api_session_port, db_manager)
    )

    @app.route("/api/v1/signup", methods=["POST"])
    async def signup_route():
        return await register_user(register_user_uc)

    @app.route("/api/v1/login", methods=["POST"])
    async def login_route():
        return await user_login(user_login_uc)

    @app.route("/api/v1/logout", methods=["POST"])
    async def logout_route():
        return await logout(user_logout_uc)

    @app.route(STATUS_URL, methods=["GET"])
    async def status_route():
        return await status(get_status_uc)

    @app.route(SETTINGS_URL, methods=["GET"])
    async def settings_route():
        return await get_settings(get_settings_uc)

    @app.route(PING_URL, methods=["GET"])
    async def ping_route():
        return {"ok": True}, 200

    @app.route("/oauth/callback", methods=["GET"])
    async def oauth_callback_route():
        return "", 200

    yield SimpleNamespace(
        app=app,
        db_manager=db_manager,
        user_login_uc=user_login_uc,
    )

    await db_client.silent_close()


@pytest_asyncio.fixture
async def http(env):
    async with env.app.test_client() as c:
        yield c


@pytest_asyncio.fixture
async def other_http(env):
    async with env.app.test_client() as c:
        yield c


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _signup(client):
    response = await client.post(
        "/api/v1/signup", json={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 200
    return (await response.get_json())["token"]


async def _login(client, username=USERNAME, password=PASSWORD):
    return await client.post(
        "/api/v1/login", json={"username": username, "password": password}
    )


async def _status(client, headers=None):
    response = await client.get(STATUS_URL, headers=headers or {})
    assert response.status_code == 200
    return await response.get_json()


class TestLockedServer:
    @pytest.mark.asyncio
    async def test_requests_pass_through_while_locked(self, http):
        response = await http.get(PING_URL)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_guest_signup_issues_no_token(self, http):
        response = await http.post(
            "/api/v1/signup", json={"username": USERNAME, "guest": True}
        )

        assert response.status_code == 204
        assert (await http.get(PING_URL)).status_code == 200


class TestSessionIssuing:
    @pytest.mark.asyncio
    async def test_signup_token_grants_access(self, http):
        token = await _signup(http)

        response = await http.get(SETTINGS_URL, headers=_auth(token))
        assert response.status_code == 200

        body = await _status(http, _auth(token))
        assert body["status"] == "UNLOCKED"
        assert body["user"]["username"] == USERNAME

    @pytest.mark.asyncio
    async def test_bearer_scheme_is_case_insensitive(self, http):
        token = await _signup(http)

        response = await http.get(
            PING_URL, headers={"Authorization": f"bearer {token}"}
        )
        assert response.status_code == 200


class TestUnauthenticatedClient:
    @pytest.mark.asyncio
    async def test_protected_routes_reject_missing_or_forged_token(
        self, http, other_http
    ):
        await _signup(http)

        for headers in ({}, _auth("forged"), {"Authorization": "Basic abc"}):
            response = await other_http.get(SETTINGS_URL, headers=headers)
            assert response.status_code == 401
            body = await response.get_json()
            assert body["code"] == "NOT_LOGGED"

    @pytest.mark.asyncio
    async def test_status_is_masked_as_locked(self, http, other_http):
        await _signup(http)

        body = await _status(other_http)

        assert body["status"] == "LOCKED"
        assert body["user"] is None
        assert body["lastLogged"] == USERNAME

    @pytest.mark.asyncio
    async def test_logout_requires_session(self, http, other_http):
        token = await _signup(http)

        response = await other_http.post("/api/v1/logout")
        assert response.status_code == 401

        assert (await http.get(PING_URL, headers=_auth(token))).status_code == 200

    @pytest.mark.asyncio
    async def test_public_paths_stay_reachable(self, http, other_http):
        await _signup(http)

        assert (await other_http.get("/static/logo.png")).status_code == 200
        assert (await other_http.get("/oauth/callback")).status_code == 200
        preflight = await other_http.options(
            SETTINGS_URL,
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert preflight.status_code != 401


class TestLoginWhileUnlocked:
    @pytest.mark.asyncio
    async def test_second_client_gets_own_token_with_valid_credentials(
        self, http, other_http
    ):
        first_token = await _signup(http)

        response = await _login(other_http)

        assert response.status_code == 200
        second_token = (await response.get_json())["token"]
        assert second_token != first_token
        assert (
            await other_http.get(PING_URL, headers=_auth(second_token))
        ).status_code == 200
        assert (await http.get(PING_URL, headers=_auth(first_token))).status_code == 200

    @pytest.mark.asyncio
    async def test_wrong_password_is_rejected(self, http, other_http):
        await _signup(http)

        response = await _login(other_http, password="wrongPassword1")

        assert response.status_code == 401
        assert (await other_http.get(PING_URL)).status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_username_is_rejected(self, http, other_http):
        await _signup(http)

        response = await _login(other_http, username="intruder")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_server_side_unlock_requires_client_login(self, env, http):
        token = await _signup(http)
        await http.post("/api/v1/logout", headers=_auth(token))

        await env.user_login_uc.execute(LoginRequest(USERNAME, PASSWORD))

        assert (await http.get(PING_URL)).status_code == 401
        assert (await _status(http))["status"] == "LOCKED"

        response = await _login(http)
        assert response.status_code == 200
        new_token = (await response.get_json())["token"]
        assert (await http.get(PING_URL, headers=_auth(new_token))).status_code == 200


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_revokes_every_session(self, http, other_http):
        first_token = await _signup(http)
        second_token = (await (await _login(other_http)).get_json())["token"]

        response = await http.post("/api/v1/logout", headers=_auth(first_token))
        assert response.status_code == 204

        relogin = await _login(http)
        assert relogin.status_code == 200
        new_token = (await relogin.get_json())["token"]

        for stale in (first_token, second_token):
            assert (await http.get(PING_URL, headers=_auth(stale))).status_code == 401
        assert (await http.get(PING_URL, headers=_auth(new_token))).status_code == 200


class TestVerifyPassword:
    @pytest.mark.asyncio
    async def test_checks_password_against_encrypted_database(self, env, http):
        assert await env.db_manager.verify_password(PASSWORD) is False

        await _signup(http)

        assert await env.db_manager.verify_password(PASSWORD) is True
        assert await env.db_manager.verify_password("wrongPassword1") is False
        assert await env.db_manager.verify_password("") is False
