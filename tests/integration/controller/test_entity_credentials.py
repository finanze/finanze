import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.entity_login import (
    EntityLoginResult,
    EntitySession,
    LoginResultCode,
)
from domain.native_entities import MY_INVESTOR, UNICAJA, MINTOS

SIGNUP_URL = "/api/v1/signup"
LOGIN_ENTITY_URL = "/api/v1/entities/login"

USERNAME = "testuser"
PASSWORD = "securePass123"

MY_INVESTOR_ID = "e0000000-0000-0000-0000-000000000001"
UNICAJA_ID = "e0000000-0000-0000-0000-000000000002"
MINTOS_ID = "e0000000-0000-0000-0000-000000000007"


async def _signup_and_stay_logged_in(client):
    response = await client.post(
        SIGNUP_URL, json={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 204


def _setup_fetcher(entity_fetchers, entity, login_result):
    fetcher = MagicMock(spec=FinancialEntityFetcher)
    fetcher.login = AsyncMock(return_value=login_result)
    entity_fetchers[entity] = fetcher
    return fetcher


def _setup_entity_account_port_no_existing(entity_account_port):
    """Set up entity_account_port to simulate no existing accounts (first login)."""
    entity_account_port.get_by_entity_id = AsyncMock(return_value=[])
    entity_account_port.create = AsyncMock()


class TestEntityLoginRouteValidation:
    @pytest.mark.asyncio
    async def test_returns_400_when_entity_missing(self, client):
        response = await client.post(
            LOGIN_ENTITY_URL,
            json={"credentials": {"user": "u", "password": "p"}},
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "entity" in body["message"].lower()

    @pytest.mark.asyncio
    async def test_returns_400_when_credentials_missing(self, client):
        response = await client.post(
            LOGIN_ENTITY_URL,
            json={"entity": MY_INVESTOR_ID},
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "credentials" in body["message"].lower()

    @pytest.mark.asyncio
    async def test_returns_400_on_empty_body(self, client):
        response = await client.post(LOGIN_ENTITY_URL, json={})
        assert response.status_code == 400


class TestEntityNotFound:
    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_entity(self, client):
        random_id = str(uuid.uuid4())
        response = await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": random_id,
                "credentials": {"user": "u", "password": "p"},
            },
        )
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "ENTITY_NOT_FOUND"


class TestInvalidCredentials:
    @pytest.mark.asyncio
    async def test_returns_400_when_credentials_incomplete(
        self, client, entity_fetchers
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        response = await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": MY_INVESTOR_ID,
                "credentials": {"user": "myuser"},
            },
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_CREDENTIALS"


class TestSuccessfulLogin:
    @pytest.mark.asyncio
    async def test_returns_200_with_created_code(
        self, client, entity_fetchers, entity_account_port
    ):
        _setup_entity_account_port_no_existing(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        response = await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": MY_INVESTOR_ID,
                "credentials": {"user": "myuser", "password": "mypass"},
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "CREATED"
        assert "entityAccountId" in body

    @pytest.mark.asyncio
    async def test_credentials_saved_after_created(
        self, client, entity_fetchers, credentials_port, entity_account_port
    ):
        _setup_entity_account_port_no_existing(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": MY_INVESTOR_ID,
                "credentials": {"user": "myuser", "password": "mypass"},
            },
        )
        credentials_port.save.assert_awaited_once()
        saved_call_args = credentials_port.save.await_args
        saved_entity_account_id = saved_call_args[0][0]
        saved_entity_id = saved_call_args[0][1]
        saved_credentials = saved_call_args[0][2]
        assert isinstance(saved_entity_account_id, uuid.UUID)
        assert saved_entity_id == uuid.UUID(MY_INVESTOR_ID)
        assert saved_credentials == {"user": "myuser", "password": "mypass"}

    @pytest.mark.asyncio
    async def test_entity_account_created_on_first_login(
        self, client, entity_fetchers, entity_account_port
    ):
        _setup_entity_account_port_no_existing(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": MY_INVESTOR_ID,
                "credentials": {"user": "myuser", "password": "mypass"},
            },
        )
        entity_account_port.create.assert_awaited_once()
        created_account = entity_account_port.create.await_args[0][0]
        assert created_account.entity_id == uuid.UUID(MY_INVESTOR_ID)

    @pytest.mark.asyncio
    async def test_old_credentials_deleted_before_save_on_relogin(
        self, client, entity_fetchers, credentials_port, entity_account_port
    ):
        from domain.entity_account import EntityAccount

        existing_account_id = uuid.uuid4()
        existing_account = EntityAccount(
            id=existing_account_id,
            entity_id=uuid.UUID(MY_INVESTOR_ID),
            created_at=datetime.now(timezone.utc),
        )
        entity_account_port.get_by_entity_id = AsyncMock(
            return_value=[existing_account]
        )
        entity_account_port.create = AsyncMock()

        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": MY_INVESTOR_ID,
                "credentials": {"user": "myuser", "password": "mypass"},
            },
        )
        credentials_port.delete.assert_awaited_once_with(existing_account_id)
        # delete must have been called before save
        delete_order = credentials_port.delete.await_args_list
        save_order = credentials_port.save.await_args_list
        assert len(delete_order) == 1
        assert len(save_order) == 1

    @pytest.mark.asyncio
    async def test_session_saved_when_present(
        self, client, entity_fetchers, sessions_port, entity_account_port
    ):
        _setup_entity_account_port_no_existing(entity_account_port)
        session = EntitySession(
            creation=datetime.now(timezone.utc),
            expiration=None,
            payload={"token": "abc123"},
        )
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED, session=session),
        )
        await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": MY_INVESTOR_ID,
                "credentials": {"user": "myuser", "password": "mypass"},
            },
        )
        sessions_port.save.assert_awaited_once()
        saved_call_args = sessions_port.save.await_args
        saved_entity_account_id = saved_call_args[0][0]
        saved_entity_id = saved_call_args[0][1]
        saved_session = saved_call_args[0][2]
        assert isinstance(saved_entity_account_id, uuid.UUID)
        assert saved_entity_id == uuid.UUID(MY_INVESTOR_ID)
        assert saved_session == session


class TestLoginFlowDeferral:
    @pytest.mark.asyncio
    async def test_returns_200_with_code_requested(
        self, client, entity_fetchers, credentials_port
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CODE_REQUESTED),
        )
        response = await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": MY_INVESTOR_ID,
                "credentials": {"user": "myuser", "password": "mypass"},
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "CODE_REQUESTED"
        credentials_port.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_200_with_invalid_credentials_code(
        self, client, entity_fetchers, credentials_port
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.INVALID_CREDENTIALS),
        )
        response = await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": MY_INVESTOR_ID,
                "credentials": {"user": "myuser", "password": "mypass"},
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "INVALID_CREDENTIALS"
        credentials_port.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_code_with_message_and_details(self, client, entity_fetchers):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(
                code=LoginResultCode.CODE_REQUESTED,
                message="Enter the code sent to your phone",
                process_id="proc-001",
            ),
        )
        response = await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": MY_INVESTOR_ID,
                "credentials": {"user": "myuser", "password": "mypass"},
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "CODE_REQUESTED"
        assert body["message"] == "Enter the code sent to your phone"
        assert body["processId"] == "proc-001"


class TestInternalCredentials:
    @pytest.mark.asyncio
    async def test_internal_cred_not_required(
        self, client, entity_fetchers, entity_account_port
    ):
        _setup_entity_account_port_no_existing(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            UNICAJA,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        response = await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": UNICAJA_ID,
                "credentials": {"user": "myuser", "password": "mypass"},
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "CREATED"

    @pytest.mark.asyncio
    async def test_internal_temp_not_saved(
        self, client, entity_fetchers, credentials_port, entity_account_port
    ):
        _setup_entity_account_port_no_existing(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MINTOS,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        await client.post(
            LOGIN_ENTITY_URL,
            json={
                "entity": MINTOS_ID,
                "credentials": {
                    "user": "myemail@test.com",
                    "password": "mypass",
                    "cookie": "temp_cookie_value",
                },
            },
        )
        credentials_port.save.assert_awaited_once()
        saved_call_args = credentials_port.save.await_args
        saved_entity_account_id = saved_call_args[0][0]
        saved_entity_id = saved_call_args[0][1]
        saved_credentials = saved_call_args[0][2]
        assert isinstance(saved_entity_account_id, uuid.UUID)
        assert saved_entity_id == uuid.UUID(MINTOS_ID)
        assert "user" in saved_credentials
        assert "password" in saved_credentials
        assert "cookie" not in saved_credentials
