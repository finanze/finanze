import pytest

SIGNUP_URL = "/api/v1/signup"
LOGIN_URL = "/api/v1/login"
LOGOUT_URL = "/api/v1/logout"
CHANGE_PASSWORD_URL = "/api/v1/change-password"
STATUS_URL = "/api/v1/status"

USERNAME = "testuser"
PASSWORD = "securePass123"
NEW_PASSWORD = "newPass456"


async def _signup(client, username=USERNAME, password=PASSWORD):
    return await client.post(
        SIGNUP_URL, json={"username": username, "password": password}
    )


async def _login(client, username=USERNAME, password=PASSWORD):
    return await client.post(
        LOGIN_URL, json={"username": username, "password": password}
    )


async def _logout(client):
    return await client.post(LOGOUT_URL)


async def _change_password(
    client, username=USERNAME, old_password=PASSWORD, new_password=NEW_PASSWORD
):
    return await client.post(
        CHANGE_PASSWORD_URL,
        json={
            "username": username,
            "oldPassword": old_password,
            "newPassword": new_password,
        },
    )


async def _status(client):
    response = await client.get(STATUS_URL)
    assert response.status_code == 200
    return await response.get_json()


class TestSignup:
    @pytest.mark.asyncio
    async def test_returns_204_on_success(self, client):
        response = await _signup(client)
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_returns_400_when_username_missing(self, client):
        response = await client.post(SIGNUP_URL, json={"password": "p"})
        assert response.status_code == 400
        body = await response.get_json()
        assert "Username not provided" in body["message"]

    @pytest.mark.asyncio
    async def test_returns_400_when_password_missing(self, client):
        response = await client.post(SIGNUP_URL, json={"username": "u"})
        assert response.status_code == 400
        body = await response.get_json()
        assert "Password not provided" in body["message"]

    @pytest.mark.asyncio
    async def test_returns_400_on_empty_body(self, client):
        response = await client.post(SIGNUP_URL, json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_409_when_user_already_exists(self, client, monkeypatch):
        monkeypatch.setenv("MULTI_USER", "1")
        await _signup(client)
        await _logout(client)
        response = await _signup(client)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_returns_error_when_already_logged_in(self, client):
        await _signup(client)
        response = await _signup(client, username="other_user")
        assert response.status_code >= 400


class TestLogin:
    @pytest.mark.asyncio
    async def test_returns_204_on_success(self, client):
        await _signup(client)
        await _logout(client)
        response = await _login(client)
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_returns_400_when_username_missing(self, client):
        response = await client.post(LOGIN_URL, json={"password": "p"})
        assert response.status_code == 400
        body = await response.get_json()
        assert "Username not provided" in body["message"]

    @pytest.mark.asyncio
    async def test_returns_400_when_password_missing(self, client):
        response = await client.post(LOGIN_URL, json={"username": "u"})
        assert response.status_code == 400
        body = await response.get_json()
        assert "Password not provided" in body["message"]

    @pytest.mark.asyncio
    async def test_returns_404_when_user_not_found(self, client):
        response = await _login(client, username="nonexistent")
        assert response.status_code == 404
        body = await response.get_json()
        assert "Username not found" in body["message"]

    @pytest.mark.asyncio
    async def test_returns_401_on_wrong_password(self, client):
        await _signup(client)
        await _logout(client)
        response = await _login(client, password="wrongPassword")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_409_when_already_logged_in(self, client):
        await _signup(client)
        response = await _login(client)
        assert response.status_code == 409
        body = await response.get_json()
        assert "already logged in" in body["message"].lower()


class TestLogout:
    @pytest.mark.asyncio
    async def test_returns_204_on_success(self, client):
        await _signup(client)
        response = await _logout(client)
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_returns_204_when_already_locked(self, client):
        response = await _logout(client)
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_returns_204_on_double_logout(self, client):
        await _signup(client)
        first = await _logout(client)
        second = await _logout(client)
        assert first.status_code == 204
        assert second.status_code == 204


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_returns_204_on_success(self, client):
        await _signup(client)
        await _logout(client)
        response = await _change_password(client)
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_returns_400_when_username_missing(self, client):
        response = await client.post(
            CHANGE_PASSWORD_URL,
            json={"oldPassword": "old", "newPassword": "new"},
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "Username not provided" in body["message"]

    @pytest.mark.asyncio
    async def test_returns_400_when_old_password_missing(self, client):
        response = await client.post(
            CHANGE_PASSWORD_URL,
            json={"username": "u", "newPassword": "new"},
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "Old password not provided" in body["message"]

    @pytest.mark.asyncio
    async def test_returns_400_when_new_password_missing(self, client):
        response = await client.post(
            CHANGE_PASSWORD_URL,
            json={"username": "u", "oldPassword": "old"},
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "New password not provided" in body["message"]

    @pytest.mark.asyncio
    async def test_returns_400_when_passwords_are_same(self, client):
        await _signup(client)
        await _logout(client)
        response = await _change_password(
            client, old_password=PASSWORD, new_password=PASSWORD
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_404_when_user_not_found(self, client):
        response = await _change_password(client, username="nonexistent")
        assert response.status_code == 404
        body = await response.get_json()
        assert "Username not found" in body["message"]

    @pytest.mark.asyncio
    async def test_returns_400_when_logged_in(self, client):
        await _signup(client)
        response = await _change_password(client)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_401_on_wrong_old_password(self, client):
        await _signup(client)
        await _logout(client)
        response = await _change_password(client, old_password="wrongPassword")
        assert response.status_code == 401


class TestStatusEndpoint:
    @pytest.mark.asyncio
    async def test_status_locked_before_signup(self, client):
        body = await _status(client)
        assert body["status"] == "LOCKED"
        assert body["user"] is None
        assert body["lastLogged"] is None
        assert body["server"]["version"] == "0.0.0-test"

    @pytest.mark.asyncio
    async def test_status_unlocked_after_signup(self, client):
        await _signup(client)
        body = await _status(client)
        assert body["status"] == "UNLOCKED"
        assert body["user"] is not None
        assert body["user"]["username"] == USERNAME
        assert body["lastLogged"] == USERNAME

    @pytest.mark.asyncio
    async def test_status_locked_after_logout(self, client):
        await _signup(client)
        await _logout(client)
        body = await _status(client)
        assert body["status"] == "LOCKED"
        assert body["user"] is None
        assert body["lastLogged"] == USERNAME

    @pytest.mark.asyncio
    async def test_status_unlocked_after_login(self, client):
        await _signup(client)
        await _logout(client)
        await _login(client)
        body = await _status(client)
        assert body["status"] == "UNLOCKED"
        assert body["user"]["username"] == USERNAME

    @pytest.mark.asyncio
    async def test_status_contains_server_info(self, client):
        body = await _status(client)
        assert body["server"]["version"] == "0.0.0-test"
        assert body["server"]["platform_type"] == "MACOS"
        assert "features" in body


class TestMigrationsAfterSignup:
    @pytest.mark.asyncio
    async def test_all_migrations_applied(self, client, db_client):
        await _signup(client)

        from infrastructure.repository.db.version_registry import versions

        async with db_client.read() as cursor:
            await cursor.execute("SELECT name FROM migrations ORDER BY rowid")
            rows = await cursor.fetchall()

        applied_names = [row["name"] for row in rows]
        expected_names = [v.name for v in versions]
        assert applied_names == expected_names
        assert len(applied_names) == len(versions)

    @pytest.mark.asyncio
    async def test_migrations_table_exists_with_correct_schema(self, client, db_client):
        await _signup(client)

        async with db_client.read() as cursor:
            await cursor.execute("PRAGMA table_info(migrations)")
            columns = await cursor.fetchall()

        column_names = [col["name"] for col in columns]
        assert "name" in column_names
        assert "applied_at" in column_names

    @pytest.mark.asyncio
    async def test_core_tables_exist_after_signup(self, client, db_client):
        await _signup(client)

        async with db_client.read() as cursor:
            await cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            rows = await cursor.fetchall()

        table_names = [row["name"] for row in rows]
        assert "migrations" in table_names
        assert "sys_config" in table_names


class TestFullUserLifecycle:
    @pytest.mark.asyncio
    async def test_register_logout_login_logout_flow(self, client):
        signup_resp = await _signup(client)
        assert signup_resp.status_code == 204

        logout_resp = await _logout(client)
        assert logout_resp.status_code == 204

        login_resp = await _login(client)
        assert login_resp.status_code == 204

        logout_resp = await _logout(client)
        assert logout_resp.status_code == 204

    @pytest.mark.asyncio
    async def test_register_change_password_login_with_new(self, client):
        await _signup(client)
        await _logout(client)

        change_resp = await _change_password(client)
        assert change_resp.status_code == 204

        old_login_resp = await _login(client, password=PASSWORD)
        assert old_login_resp.status_code == 401

        new_login_resp = await _login(client, password=NEW_PASSWORD)
        assert new_login_resp.status_code == 204

    @pytest.mark.asyncio
    async def test_full_lifecycle_with_status_checks(self, client):
        body = await _status(client)
        assert body["status"] == "LOCKED"
        assert body["user"] is None

        await _signup(client)
        body = await _status(client)
        assert body["status"] == "UNLOCKED"
        assert body["user"]["username"] == USERNAME

        await _logout(client)
        body = await _status(client)
        assert body["status"] == "LOCKED"
        assert body["user"] is None
        assert body["lastLogged"] == USERNAME

        await _login(client)
        body = await _status(client)
        assert body["status"] == "UNLOCKED"
        assert body["user"]["username"] == USERNAME

        await _logout(client)
        body = await _status(client)
        assert body["status"] == "LOCKED"
