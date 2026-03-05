import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.entity import Feature
from domain.entity_login import (
    EntityLoginResult,
    EntitySession,
    LoginResultCode,
)
from domain.fetch_record import FetchRecord
from domain.global_position import GlobalPosition
from domain.native_entities import MY_INVESTOR

FETCH_URL = "/api/v1/data/fetch/financial"

MY_INVESTOR_ID = "e0000000-0000-0000-0000-000000000001"


def _setup_fetcher(entity_fetchers, entity, login_result, position=None):
    fetcher = MagicMock(spec=FinancialEntityFetcher)
    fetcher.login = AsyncMock(return_value=login_result)
    if position is None:
        position = _make_position()
    fetcher.global_position = AsyncMock(return_value=position)
    fetcher.auto_contributions = AsyncMock(return_value=None)
    fetcher.transactions = AsyncMock(return_value=None)
    entity_fetchers[entity] = fetcher
    return fetcher


def _make_position():
    return GlobalPosition(
        id=uuid.uuid4(),
        entity=MY_INVESTOR,
        products={},
    )


class TestFetchRouteValidation:
    @pytest.mark.asyncio
    async def test_returns_400_when_entity_missing(self, client):
        response = await client.post(
            FETCH_URL,
            json={"features": ["POSITION"]},
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "entity" in body["message"].lower()

    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_feature(self, client):
        response = await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["NONEXISTENT"]},
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "feature" in body["message"].lower()


class TestEntityNotFound:
    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_entity(self, client):
        random_id = str(uuid.uuid4())
        response = await client.post(
            FETCH_URL,
            json={"entity": random_id, "features": ["POSITION"]},
        )
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "ENTITY_NOT_FOUND"


class TestFeatureNotSupported:
    @pytest.mark.asyncio
    async def test_returns_feature_not_supported(
        self, client, entity_fetchers, credentials_port, last_fetches_port
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        response = await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["HISTORIC"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "FEATURE_NOT_SUPPORTED"


class TestNoCredentials:
    @pytest.mark.asyncio
    async def test_returns_no_credentials_available(
        self, client, entity_fetchers, credentials_port, last_fetches_port
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "NO_CREDENTIALS_AVAILABLE"


class TestInvalidStoredCredentials:
    @pytest.mark.asyncio
    async def test_returns_invalid_credentials_for_incomplete_stored_creds(
        self, client, entity_fetchers, credentials_port, last_fetches_port
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(return_value={"user": "myuser"})

        response = await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "INVALID_CREDENTIALS"


class TestCooldown:
    @pytest.mark.asyncio
    async def test_returns_cooldown_when_recently_fetched(
        self, client, entity_fetchers, credentials_port, last_fetches_port
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        recent_record = FetchRecord(
            entity_id=uuid.UUID(MY_INVESTOR_ID),
            feature=Feature.POSITION,
            date=datetime.now(timezone.utc),
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[recent_record])

        response = await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COOLDOWN"
        assert "lastUpdate" in body["details"]
        assert "wait" in body["details"]


class TestLoginResults:
    @pytest.mark.asyncio
    async def test_returns_code_requested(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(
                code=LoginResultCode.CODE_REQUESTED,
                message="Enter SMS code",
                process_id="proc-123",
            ),
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "CODE_REQUESTED"
        assert body["details"]["message"] == "Enter SMS code"
        assert body["details"]["processId"] == "proc-123"

    @pytest.mark.asyncio
    async def test_returns_login_required(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(
                code=LoginResultCode.LOGIN_REQUIRED,
                message="Session expired",
            ),
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "LOGIN_REQUIRED"

    @pytest.mark.asyncio
    async def test_returns_invalid_credentials_on_bad_login(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.INVALID_CREDENTIALS),
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "INVALID_CREDENTIALS"


class TestSuccessfulFetch:
    @pytest.mark.asyncio
    async def test_returns_completed_with_position(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
    ):
        position = _make_position()
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_position_saved(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        position_port,
    ):
        position = _make_position()
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        position_port.save.assert_awaited_once_with(position)

    @pytest.mark.asyncio
    async def test_last_fetch_recorded(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        last_fetches_port.save.assert_awaited_once()
        saved_records = last_fetches_port.save.await_args[0][0]
        assert len(saved_records) == 1
        assert saved_records[0].feature == Feature.POSITION

    @pytest.mark.asyncio
    async def test_credentials_usage_updated_on_created_login(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        credentials_port.update_last_usage.assert_awaited_once_with(
            uuid.UUID(MY_INVESTOR_ID)
        )
        credentials_port.update_expiration.assert_awaited_once_with(
            uuid.UUID(MY_INVESTOR_ID), None
        )

    @pytest.mark.asyncio
    async def test_session_saved_on_created_login(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
    ):
        session = EntitySession(
            creation=datetime.now(timezone.utc),
            expiration=None,
            payload={"token": "abc"},
        )
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED, session=session),
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        sessions_port.delete.assert_awaited_once_with(uuid.UUID(MY_INVESTOR_ID))
        sessions_port.save.assert_awaited_once_with(uuid.UUID(MY_INVESTOR_ID), session)


class TestResumedLogin:
    @pytest.mark.asyncio
    async def test_completed_with_resumed_login_skips_credential_updates(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
    ):
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.RESUMED),
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"
        credentials_port.update_last_usage.assert_not_awaited()
        sessions_port.save.assert_not_awaited()


class TestDefaultFeatures:
    @pytest.mark.asyncio
    async def test_defaults_to_position_when_no_features(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        position_port,
    ):
        position = _make_position()
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entity": MY_INVESTOR_ID},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"
        position_port.save.assert_awaited_once_with(position)


class TestMultipleFeatures:
    @pytest.mark.asyncio
    async def test_fetch_position_and_auto_contributions(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
    ):
        fetcher = _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={
                "entity": MY_INVESTOR_ID,
                "features": ["POSITION", "AUTO_CONTRIBUTIONS"],
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"
        fetcher.global_position.assert_awaited_once()
        fetcher.auto_contributions.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fetch_with_transactions(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        transaction_port,
    ):
        fetcher = _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        transaction_port.get_refs_by_entity = AsyncMock(return_value=set())
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={
                "entity": MY_INVESTOR_ID,
                "features": ["TRANSACTIONS"],
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"
        fetcher.transactions.assert_awaited_once()
