import sqlite3
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionTargetType,
    PeriodicContribution,
)
from domain.data_init import DatasourceInitContext
from domain.dezimal import Dezimal
from domain.entity import Feature
from domain.entity_account import EntityAccount
from domain.entity_login import (
    ChallengeType,
    EntityLoginResult,
    EntitySession,
    LoginConfirmationType,
    LoginResultCode,
)
from domain.fetch_record import DataSource, FetchRecord
from domain.global_position import GlobalPosition, ProductType
from domain.native_entities import ING, MY_INVESTOR
from domain.transactions import AccountTx, Transactions, TxType
from infrastructure.client.entity.financial.ing.ing_client import INGAPIClient
from infrastructure.client.entity.financial.ing.ing_fetcher import INGFetcher
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.entity.entity_repository import EntitySQLRepository
from infrastructure.repository.entity_account.entity_account_repository import (
    EntityAccountRepository,
)
from infrastructure.repository.fetch.fetch_pointers_repository import (
    FetchPointersRepository,
)
from infrastructure.repository.transaction.transaction_repository import (
    TransactionSQLRepository,
)

FETCH_URL = "/api/v1/data/fetch/financial"
GET_POSITIONS_URL = "/api/v1/positions"
GET_TRANSACTIONS_URL = "/api/v1/transactions"
GET_CONTRIBUTIONS_URL = "/api/v1/contributions"

MY_INVESTOR_ID = "e0000000-0000-0000-0000-000000000001"
ENTITY_ACCOUNT_ID = "a0000000-0000-0000-0000-000000000001"


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


def _make_entity_account():
    return EntityAccount(
        id=uuid.UUID(ENTITY_ACCOUNT_ID),
        entity_id=uuid.UUID(MY_INVESTOR_ID),
        created_at=datetime.now(timezone.utc),
    )


def _setup_entity_account(entity_account_port):
    entity_account_port.get_by_id = AsyncMock(return_value=_make_entity_account())


class TestFetchRouteValidation:
    @pytest.mark.asyncio
    async def test_returns_400_when_entity_account_missing(self, client):
        response = await client.post(
            FETCH_URL,
            json={"features": ["POSITION"]},
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "entity account" in body["message"].lower()

    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_feature(self, client, entity_account_port):
        _setup_entity_account(entity_account_port)
        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["NONEXISTENT"]},
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "feature" in body["message"].lower()


class TestEntityNotFound:
    @pytest.mark.asyncio
    async def test_returns_not_connected_for_unknown_account(
        self, client, entity_account_port
    ):
        entity_account_port.get_by_id = AsyncMock(return_value=None)
        random_id = str(uuid.uuid4())
        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": random_id, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "NOT_CONNECTED"


class TestFeatureNotSupported:
    @pytest.mark.asyncio
    async def test_returns_feature_not_supported(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["HISTORIC"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "FEATURE_NOT_SUPPORTED"


class TestNoCredentials:
    @pytest.mark.asyncio
    async def test_returns_no_credentials_available(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "NO_CREDENTIALS_AVAILABLE"


class TestInvalidStoredCredentials:
    @pytest.mark.asyncio
    async def test_returns_invalid_credentials_for_incomplete_stored_creds(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(return_value={"user": "myuser"})

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "INVALID_CREDENTIALS"


class TestCooldown:
    @pytest.mark.asyncio
    async def test_returns_cooldown_when_recently_fetched(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
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
        last_fetches_port.get_by_entity_account_id = AsyncMock(
            return_value=[recent_record]
        )

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
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
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(
                code=LoginResultCode.CODE_REQUESTED,
                message="Enter SMS code",
                process_id="proc-123",
            ),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
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
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(
                code=LoginResultCode.LOGIN_REQUIRED,
                message="Session expired",
            ),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
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
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.INVALID_CREDENTIALS),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
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
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        position = _make_position()
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"
        assert "data" not in body

    @pytest.mark.asyncio
    async def test_position_saved(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        position_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        position = _make_position()
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        position_port.save.assert_awaited_once_with(position)

        # Read-after-write: verify position via GET /positions
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={MY_INVESTOR: [position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        pos_body = await get_resp.get_json()
        assert MY_INVESTOR_ID in pos_body["positions"]
        assert len(pos_body["positions"][MY_INVESTOR_ID]) == 1

    @pytest.mark.asyncio
    async def test_last_fetch_recorded(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
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
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        credentials_port.update_last_usage.assert_awaited_once_with(
            uuid.UUID(ENTITY_ACCOUNT_ID)
        )
        credentials_port.update_expiration.assert_awaited_once_with(
            uuid.UUID(ENTITY_ACCOUNT_ID), None
        )

    @pytest.mark.asyncio
    async def test_session_saved_on_created_login(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
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
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        sessions_port.delete.assert_awaited_once_with(uuid.UUID(ENTITY_ACCOUNT_ID))
        sessions_port.save.assert_awaited_once_with(
            uuid.UUID(ENTITY_ACCOUNT_ID),
            uuid.UUID(MY_INVESTOR_ID),
            session,
        )


class TestResumedLogin:
    @pytest.mark.asyncio
    async def test_completed_with_resumed_login_skips_credential_updates(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.RESUMED),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
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
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        position = _make_position()
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID},
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
        position_port,
        auto_contr_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        test_contrib = PeriodicContribution(
            id=uuid.uuid4(),
            alias="Auto DCA",
            target="AAPL",
            target_name="Apple",
            target_type=ContributionTargetType.STOCK_ETF,
            amount=Dezimal("100"),
            currency="EUR",
            since=date(2025, 1, 1),
            until=None,
            frequency=ContributionFrequency.MONTHLY,
            active=True,
            source=DataSource.REAL,
        )
        auto_contribs = AutoContributions(periodic=[test_contrib])
        fetcher = _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        fetcher.auto_contributions = AsyncMock(return_value=auto_contribs)
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={
                "entityAccountId": ENTITY_ACCOUNT_ID,
                "features": ["POSITION", "AUTO_CONTRIBUTIONS"],
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"
        fetcher.global_position.assert_awaited_once()
        fetcher.auto_contributions.assert_awaited_once()

        # Read-after-write: verify position via GET /positions
        position_port.save.assert_awaited_once()
        saved_position = position_port.save.await_args[0][0]
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={MY_INVESTOR: [saved_position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        pos_body = await get_resp.get_json()
        assert MY_INVESTOR_ID in pos_body["positions"]

        # Read-after-write: verify contributions via GET /contributions
        auto_contr_port.save.assert_awaited_once()
        saved_contribs = auto_contr_port.save.await_args[0][1]
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={MY_INVESTOR: saved_contribs}
        )
        get_resp2 = await client.get(GET_CONTRIBUTIONS_URL)
        assert get_resp2.status_code == 200
        contrib_body = await get_resp2.get_json()

        assert MY_INVESTOR_ID in contrib_body
        periodic = contrib_body[MY_INVESTOR_ID]["periodic"]
        assert len(periodic) == 1
        assert periodic[0]["alias"] == "Auto DCA"
        assert periodic[0]["target"] == "AAPL"
        assert periodic[0]["amount"] == 100.0
        assert periodic[0]["source"] == "REAL"

    @pytest.mark.asyncio
    async def test_fetch_with_transactions(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        transaction_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        test_tx = AccountTx(
            id=uuid.uuid4(),
            ref="TX-FETCH-001",
            name="Fetched Transfer",
            amount=Dezimal("1500"),
            currency="EUR",
            type=TxType.TRANSFER_IN,
            date=datetime.now(timezone.utc),
            entity=MY_INVESTOR,
            source=DataSource.REAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal("0"),
            retentions=Dezimal("0"),
        )
        fetcher = _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        fetcher.transactions = AsyncMock(
            return_value=Transactions(account=[test_tx], investment=[])
        )
        transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={
                "entityAccountId": ENTITY_ACCOUNT_ID,
                "features": ["TRANSACTIONS"],
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"
        fetcher.transactions.assert_awaited_once()
        transaction_port.save.assert_awaited_once()

        # Read-after-write: verify transactions via GET /transactions
        saved_txs = transaction_port.save.await_args[0][0]
        saved_tx = saved_txs.account[0]
        transaction_port.get_by_filters = AsyncMock(return_value=[saved_tx])
        get_resp = await client.get(GET_TRANSACTIONS_URL)
        assert get_resp.status_code == 200
        tx_body = await get_resp.get_json()

        txs = tx_body["transactions"]
        assert len(txs) == 1
        assert txs[0]["name"] == "Fetched Transfer"
        assert txs[0]["amount"] == 1500.0
        assert txs[0]["source"] == "REAL"
        assert txs[0]["currency"] == "EUR"


class TestINGAccountTransactions:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("deep", [False, True])
    async def test_fetch_persists_account_transactions_and_pointers(
        self,
        client,
        db_client,
        entity_fetchers,
        credentials_port,
        sessions_port,
        last_fetches_port,
        entity_account_port,
        transaction_port,
        fetch_pointers_port,
        transaction_handler_port,
        deep,
    ):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        db_client.set_connection(connection)
        await DatabaseUpgrader(
            db_client, versions, DatasourceInitContext(config=AsyncMock())
        ).upgrade()
        entity_repo = EntitySQLRepository(db_client)
        if await entity_repo.get_by_id(ING.id) is None:
            await entity_repo.insert(ING)
        account = EntityAccount(
            id=uuid.UUID(ENTITY_ACCOUNT_ID),
            entity_id=ING.id,
            created_at=datetime.now(tzlocal()),
        )
        account_repo = EntityAccountRepository(db_client)
        await account_repo.create(account)
        entity_account_port.get_by_id.side_effect = account_repo.get_by_id

        tx_repo = TransactionSQLRepository(db_client)
        pointer_repo = FetchPointersRepository(db_client)
        for method in (
            "save",
            "get_refs_by_entity_account",
            "get_by_filters",
            "delete_by_entity_account_id",
        ):
            getattr(transaction_port, method).side_effect = getattr(tx_repo, method)
        for method in (
            "save",
            "get_by_entity_account_id",
            "delete_by_entity_account_id",
        ):
            getattr(fetch_pointers_port, method).side_effect = getattr(
                pointer_repo, method
            )
        transaction_handler_port.start.side_effect = TransactionHandler(db_client).start

        today = datetime.now(tzlocal()).date()
        bank_client = AsyncMock(spec=INGAPIClient)
        bank_client.get_position.return_value = {
            "products": [
                {
                    "uuid": "account-product",
                    "type": "CURRENT_ACCOUNT",
                    "denominationCurrency": "EUR",
                    "identifiers": [{"type": "IBAN", "value": "es12 3456 7890"}],
                }
            ],
            "legacyProducts": [],
        }
        movements = [
            {
                "transactionId": {
                    "productId": "account-product",
                    "transactionSequence": sequence,
                },
                "transactionDate": today.isoformat(),
                "description": description,
                "amount": amount,
            }
            for sequence, description, amount in (
                (1, "Pago de prueba", "-10.25"),
                (2, "Ingreso de prueba", "20.50"),
            )
        ]
        bank_client.get_account_transactions.return_value = {
            "transactions": movements,
            "count": 2,
            "total": 2,
            "mayHasMoreElements": False,
        }
        fetcher = INGFetcher()
        fetcher._client = bank_client
        fetcher.login = AsyncMock(
            return_value=EntityLoginResult(code=LoginResultCode.RESUMED)
        )
        entity_fetchers[ING] = fetcher
        credentials_port.get.return_value = {
            name: "test-value" for name in ING.credentials_template
        }
        sessions_port.get.return_value = None
        last_fetches_port.get_by_entity_account_id.return_value = []

        payload = {"entityAccountId": str(account.id), "features": ["TRANSACTIONS"]}
        response = await client.post(FETCH_URL, json=payload)
        assert response.status_code == 200
        assert (await response.get_json())["code"] == "COMPLETED"
        bank_client.get_account_transactions.assert_awaited_once_with(
            "account-product",
            today - relativedelta(months=3),
            offset=0,
            limit=100,
            to_date=today,
        )

        read_response = await client.get(GET_TRANSACTIONS_URL)
        assert read_response.status_code == 200
        rows = (await read_response.get_json())["transactions"]
        assert {row["name"]: row["type"] for row in rows} == {
            "Pago de prueba": "OUTFLOW",
            "Ingreso de prueba": "INFLOW",
        }
        assert {Dezimal(str(row["amount"])) for row in rows} == {
            Dezimal("10.25"),
            Dezimal("20.50"),
        }
        assert all(row["iban"] == "ES1234567890" for row in rows)
        assert all(row["source"] == "REAL" for row in rows)
        first_ids = {row["id"] for row in rows}
        assert await tx_repo.get_refs_by_entity_account(account.id) == {
            "account-product:1",
            "account-product:2",
        }
        pointers = await pointer_repo.get_by_entity_account_id(account.id)
        assert len(pointers) == 1
        assert pointers[0].key == "account_txs:ES1234567890"
        assert pointers[0].threshold == today

        response = await client.post(FETCH_URL, json={**payload, "deep": deep})
        assert response.status_code == 200
        assert (await response.get_json())["code"] == "COMPLETED"
        assert bank_client.get_account_transactions.await_args.args[1] == (
            today - relativedelta(months=3) if deep else today - relativedelta(days=7)
        )
        read_response = await client.get(GET_TRANSACTIONS_URL)
        rows = (await read_response.get_json())["transactions"]
        assert len(rows) == 2
        second_ids = {row["id"] for row in rows}
        assert first_ids.isdisjoint(second_ids) if deep else first_ids == second_ids
        assert await pointer_repo.get_by_entity_account_id(account.id) == pointers
        if deep:
            transaction_port.delete_by_entity_account_id.assert_awaited_once_with(
                account.id
            )
            fetch_pointers_port.delete_by_entity_account_id.assert_awaited_once_with(
                account.id
            )
        else:
            transaction_port.delete_by_entity_account_id.assert_not_awaited()
            fetch_pointers_port.delete_by_entity_account_id.assert_not_awaited()


class TestChallengeFlow:
    @pytest.mark.asyncio
    async def test_returns_confirmation_type_in_app(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(
                code=LoginResultCode.CODE_REQUESTED,
                message="Confirm in your app",
                confirmation_type=LoginConfirmationType.IN_APP,
                process_id="proc-app-001",
            ),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "CODE_REQUESTED"
        assert body["confirmationType"] == "IN_APP"
        assert body["details"]["message"] == "Confirm in your app"
        assert body["details"]["processId"] == "proc-app-001"

    @pytest.mark.asyncio
    async def test_returns_challenge_type_recaptcha(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(
                code=LoginResultCode.CODE_REQUESTED,
                message="Solve the captcha",
                confirmation_type=LoginConfirmationType.CHALLENGE,
                challenge_type=ChallengeType.RECAPTCHA,
                process_id="captcha-001",
            ),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "CODE_REQUESTED"
        assert body["confirmationType"] == "CHALLENGE"
        assert body["details"]["challengeType"] == "RECAPTCHA"
        assert body["details"]["processId"] == "captcha-001"

    @pytest.mark.asyncio
    async def test_returns_challenge_domain_when_provided(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(
                code=LoginResultCode.CODE_REQUESTED,
                message="Solve the captcha",
                confirmation_type=LoginConfirmationType.CHALLENGE,
                challenge_type=ChallengeType.RECAPTCHA,
                process_id="captcha-002",
                details={"challenge_domain": "myinvestor.es"},
            ),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "CODE_REQUESTED"
        assert body["confirmationType"] == "CHALLENGE"
        assert body["details"]["challengeType"] == "RECAPTCHA"
        assert body["details"]["processId"] == "captcha-002"
        assert body["details"]["challengeDomain"] == "myinvestor.es"

    @pytest.mark.asyncio
    async def test_returns_challenge_type_awswaf(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(
                code=LoginResultCode.CODE_REQUESTED,
                message="Complete WAF challenge",
                confirmation_type=LoginConfirmationType.CHALLENGE,
                challenge_type=ChallengeType.AWSWAF,
            ),
        )
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "CODE_REQUESTED"
        assert body["confirmationType"] == "CHALLENGE"
        assert body["details"]["challengeType"] == "AWSWAF"


class TestIsolatedFeaturePersist:
    @pytest.mark.asyncio
    async def test_position_saved_when_transactions_fail(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        position_port,
        transaction_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        position = _make_position()
        fetcher = _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )
        fetcher.transactions = AsyncMock(side_effect=RuntimeError("txs boom"))
        transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={
                "entityAccountId": ENTITY_ACCOUNT_ID,
                "features": ["POSITION", "TRANSACTIONS"],
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "PARTIALLY_COMPLETED"
        assert body["details"]["failedFeatures"] == ["TRANSACTIONS"]
        assert body["details"]["completedFeatures"] == ["POSITION"]
        position_port.save.assert_awaited_once_with(position)
        transaction_port.save.assert_not_awaited()
        saved_records = last_fetches_port.save.await_args[0][0]
        assert [record.feature for record in saved_records] == [Feature.POSITION]

    @pytest.mark.asyncio
    async def test_transactions_saved_when_position_fails(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        position_port,
        transaction_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        test_tx = AccountTx(
            id=uuid.uuid4(),
            ref="TX-PARTIAL-001",
            name="Fetched Transfer",
            amount=Dezimal("1500"),
            currency="EUR",
            type=TxType.TRANSFER_IN,
            date=datetime.now(timezone.utc),
            entity=MY_INVESTOR,
            source=DataSource.REAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal("0"),
            retentions=Dezimal("0"),
        )
        fetcher = _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        fetcher.global_position = AsyncMock(side_effect=RuntimeError("pos boom"))
        fetcher.transactions = AsyncMock(
            return_value=Transactions(account=[test_tx], investment=[])
        )
        transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={
                "entityAccountId": ENTITY_ACCOUNT_ID,
                "features": ["POSITION", "TRANSACTIONS"],
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "PARTIALLY_COMPLETED"
        assert body["details"]["failedFeatures"] == ["POSITION"]
        assert body["details"]["completedFeatures"] == ["TRANSACTIONS"]
        position_port.save.assert_not_awaited()
        transaction_port.save.assert_awaited_once()
        saved_records = last_fetches_port.save.await_args[0][0]
        assert [record.feature for record in saved_records] == [Feature.TRANSACTIONS]

    @pytest.mark.asyncio
    async def test_mixed_cooldown_fetches_pending_feature_only(
        self,
        client,
        entity_fetchers,
        credentials_port,
        last_fetches_port,
        sessions_port,
        position_port,
        transaction_port,
        entity_account_port,
    ):
        _setup_entity_account(entity_account_port)
        test_tx = AccountTx(
            id=uuid.uuid4(),
            ref="TX-COOL-001",
            name="Fetched Transfer",
            amount=Dezimal("1500"),
            currency="EUR",
            type=TxType.TRANSFER_IN,
            date=datetime.now(timezone.utc),
            entity=MY_INVESTOR,
            source=DataSource.REAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal("0"),
            retentions=Dezimal("0"),
        )
        fetcher = _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
        )
        fetcher.transactions = AsyncMock(
            return_value=Transactions(account=[test_tx], investment=[])
        )
        transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        last_fetches_port.get_by_entity_account_id = AsyncMock(
            return_value=[
                FetchRecord(
                    entity_id=uuid.UUID(MY_INVESTOR_ID),
                    feature=Feature.POSITION,
                    date=datetime.now(timezone.utc),
                    entity_account_id=uuid.UUID(ENTITY_ACCOUNT_ID),
                )
            ]
        )
        credentials_port.get = AsyncMock(
            return_value={"user": "myuser", "password": "mypass"}
        )
        sessions_port.get = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={
                "entityAccountId": ENTITY_ACCOUNT_ID,
                "features": ["POSITION", "TRANSACTIONS"],
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"
        assert body["details"]["completedFeatures"] == ["TRANSACTIONS"]
        fetcher.global_position.assert_not_awaited()
        fetcher.transactions.assert_awaited_once()
        position_port.save.assert_not_awaited()
        transaction_port.save.assert_awaited_once()
