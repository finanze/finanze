import sqlite3
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from dateutil.tz import tzlocal
from quart import Quart, request

from application.ports.external_entity_fetcher import ExternalEntityFetcher
from application.use_cases.fetch_external_financial_data import (
    FetchExternalFinancialDataImpl,
)
from application.use_cases.fetch_financial_data import FetchFinancialDataImpl
from application.use_cases.get_settings import GetSettingsImpl
from application.use_cases.update_settings import UpdateSettingsImpl
from domain.data_init import DatasourceInitContext
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.entity_account import EntityAccount
from domain.exception.exceptions import ExternalEntityFailed
from domain.external_entity import ExternalEntity, ExternalEntityStatus
from domain.external_integration import ExternalIntegrationId
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions, FetchResultCode
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    GlobalPosition,
    ProductType,
)
from domain.transactions import AccountTx, Transactions, TxType
from infrastructure.controller.routes.fetch_external_financial_data import (
    fetch_external_financial_data,
)
from infrastructure.controller.routes.get_settings import get_settings
from infrastructure.controller.routes.update_settings import update_settings
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.entity.entity_repository import EntitySQLRepository
from infrastructure.repository.entity_account.entity_account_repository import (
    EntityAccountRepository,
)
from infrastructure.repository.labeling.transaction_label_repository import (
    TransactionLabelRepository,
)
from infrastructure.repository.position.position_repository import PositionSQLRepository
from infrastructure.repository.settings.settings_repository import SettingsRepository
from infrastructure.repository.transaction.transaction_repository import (
    TransactionSQLRepository,
)

EXCLUDED_IBAN = "ES1234567890"


def movement(entity, ref, iban, source=DataSource.REAL):
    return AccountTx(
        id=uuid4(),
        ref=ref,
        name=ref,
        amount=Dezimal(10),
        currency="EUR",
        type=TxType.INFLOW,
        date=datetime.now(tzlocal()),
        entity=entity,
        source=source,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        iban=iban,
    )


@pytest_asyncio.fixture
async def env():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    db = DBClient(connection)
    await DatabaseUpgrader(
        db, versions, DatasourceInitContext(config=AsyncMock())
    ).upgrade()
    entity = Entity(
        id=uuid4(),
        name="External bank",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.EXTERNALLY_PROVIDED,
        icon_url=None,
    )
    entities = EntitySQLRepository(db)
    await entities.insert(entity)
    external = ExternalEntity(
        id=uuid4(),
        entity_id=entity.id,
        status=ExternalEntityStatus.LINKED,
        provider=ExternalIntegrationId.ENABLE_BANKING,
    )
    external_port = AsyncMock()
    external_port.get_by_id.return_value = external
    integrations = AsyncMock()
    integrations.get_payloads_by_type.return_value = {}
    last_fetches = AsyncMock()
    last_fetches.get_by_entity_id.return_value = []
    settings = SettingsRepository(db, MagicMock())
    positions = PositionSQLRepository(db)
    transactions = TransactionSQLRepository(db)
    classifications = TransactionLabelRepository(db)
    labeler = AsyncMock()
    provider = AsyncMock(spec=ExternalEntityFetcher)

    async def position(_request):
        return GlobalPosition(
            id=uuid4(),
            entity=entity,
            products={
                ProductType.ACCOUNT: Accounts(
                    [
                        Account(
                            id=uuid4(),
                            total=Dezimal(100),
                            currency="EUR",
                            type=AccountType.CHECKING,
                            iban=EXCLUDED_IBAN,
                        ),
                        Account(
                            id=uuid4(),
                            total=Dezimal(200),
                            currency="EUR",
                            type=AccountType.CHECKING,
                            iban="ES999",
                        ),
                    ]
                ),
            },
        )

    provider.global_position.side_effect = position
    provider.transactions.side_effect = lambda _request: Transactions(
        account=[
            movement(entity, "excluded", EXCLUDED_IBAN),
            movement(entity, "included", "ES999"),
        ]
    )
    fetch = FetchExternalFinancialDataImpl(
        entities,
        external_port,
        positions,
        {external.provider: provider},
        integrations,
        last_fetches,
        TransactionHandler(db),
        transactions,
        labeler,
        settings,
        classifications,
    )
    app = Quart(__name__)

    @app.route("/settings", methods=["GET", "POST"])
    async def settings_route():
        if request.method == "POST":
            return await update_settings(UpdateSettingsImpl(settings))
        return await get_settings(GetSettingsImpl(settings))

    @app.post("/fetch/<external_entity_id>")
    async def fetch_route(external_entity_id):
        return await fetch_external_financial_data(fetch, external_entity_id)

    yield SimpleNamespace(
        client=app.test_client(),
        entity=entity,
        external=external,
        provider=provider,
        settings=settings,
        positions=positions,
        transactions=transactions,
        classifications=classifications,
        labeler=labeler,
        entities=entities,
        db=db,
    )
    connection.close()


async def save_rules(env, values):
    response = await env.client.post(
        "/settings",
        json={
            "assets": {
                "crypto": {"stablecoins": ["USDT"]},
                "accounts": {
                    "exclusions": [{"type": "IBAN", "value": value} for value in values]
                },
            }
        },
    )
    assert response.status_code == 204


async def fetch(env, **options):
    response = await env.client.post(f"/fetch/{env.external.id}", json=options)
    assert response.status_code == 200
    return await response.get_json()


@pytest.mark.asyncio
async def test_rules_normal_fetch_deep_cleanup_and_reinclusion(env):
    assert (await fetch(env))["code"] == "COMPLETED"
    previous = await env.transactions.get_by_entity_and_source(
        env.entity.id, DataSource.REAL
    )
    included = next(tx for tx in previous.account if tx.ref == "included")
    await env.classifications.set_locked([included.id], True)
    manual = movement(env.entity, "manual", EXCLUDED_IBAN, DataSource.MANUAL)
    imported = movement(env.entity, "imported", EXCLUDED_IBAN, DataSource.SHEETS)
    await env.transactions.save(Transactions(account=[manual, imported]))

    await save_rules(env, [" es12 3456 7890 "])
    assert len((await env.transactions.get_by_entity(env.entity.id)).account) == 4
    settings_response = await env.client.get("/settings?key=assets")
    assert (await settings_response.get_json())["assets"]["accounts"]["exclusions"] == [
        {"type": "IBAN", "value": EXCLUDED_IBAN}
    ]
    assert (await fetch(env))["code"] == "COMPLETED"
    current = await env.positions.get_last_grouped_by_entity()
    assert [
        account.iban
        for account in current[env.entity].products[ProductType.ACCOUNT].entries
    ] == ["ES999"]
    assert len((await env.transactions.get_by_entity(env.entity.id)).account) == 4

    assert (await fetch(env, deep=True))["code"] == "COMPLETED"
    real = await env.transactions.get_by_entity_and_source(
        env.entity.id, DataSource.REAL
    )
    assert [tx.ref for tx in real.account] == ["included"]
    restored = await env.classifications.get_classifications_by_ids(
        [real.account[0].id]
    )
    assert restored[real.account[0].id].locked
    assert len((await env.transactions.get_by_entity(env.entity.id)).account) == 3
    await save_rules(env, [])
    assert (await env.settings.load()).assets.accounts.exclusions == []
    assert (await env.settings.load()).assets.crypto.stablecoins == ["USDT"]
    await fetch(env, deep=True)
    assert {
        tx.ref
        for tx in (
            await env.transactions.get_by_entity_and_source(
                env.entity.id, DataSource.REAL
            )
        ).account
    } == {"included", "excluded"}


@pytest.mark.asyncio
async def test_all_excluded_replaces_current_snapshot_and_real_history(env):
    await fetch(env)
    await save_rules(env, [EXCLUDED_IBAN, "ES999"])
    await fetch(env, deep=True)
    current = await env.positions.get_last_grouped_by_entity()
    assert current[env.entity].products.get(ProductType.ACCOUNT) is None
    assert (
        await env.transactions.get_by_entity_and_source(env.entity.id, DataSource.REAL)
    ).account == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["provider", "database", "labeling"])
async def test_deep_failures_preserve_stored_history(env, failure):
    await fetch(env)
    previous = await env.transactions.get_by_entity(env.entity.id)
    await save_rules(env, [EXCLUDED_IBAN])
    if failure == "provider":
        env.provider.transactions.side_effect = ExternalEntityFailed()
    elif failure == "database":
        env.transactions.save = AsyncMock(side_effect=RuntimeError("Database failed"))
    else:
        env.labeler.classify.side_effect = RuntimeError("Labeling failed")
    result = await fetch(env, features=["TRANSACTIONS"], deep=True)
    assert result["code"] == "REMOTE_FAILED"
    assert [
        tx.id for tx in (await env.transactions.get_by_entity(env.entity.id)).account
    ] == [tx.id for tx in previous.account]


@pytest.mark.asyncio
async def test_deep_cleanup_does_not_touch_another_entity(env):
    other = Entity(
        id=uuid4(),
        name="Other bank",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.EXTERNALLY_PROVIDED,
        icon_url=None,
    )
    await env.entities.insert(other)
    transaction = movement(other, "excluded", EXCLUDED_IBAN)
    await env.transactions.save(Transactions(account=[transaction]))
    await fetch(env)
    await save_rules(env, [EXCLUDED_IBAN])
    await fetch(env, features=["TRANSACTIONS"], deep=True)
    assert [
        tx.id for tx in (await env.transactions.get_by_entity(other.id)).account
    ] == [transaction.id]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"deep": "true"},
        {"deep": 1},
        {"features": []},
        {"features": ["HISTORIC"]},
        {"features": "TRANSACTIONS"},
        {"unknown": True},
        ["POSITION"],
    ],
)
async def test_external_fetch_validates_optional_body(env, body):
    response = await env.client.post(f"/fetch/{env.external.id}", json=body)
    assert response.status_code == 400
    env.provider.setup.assert_not_called()


@pytest.mark.asyncio
async def test_bodyless_external_fetch_remains_compatible(env):
    response = await env.client.post(f"/fetch/{env.external.id}")
    assert response.status_code == 200
    assert (await response.get_json())["details"]["completedFeatures"] == [
        "POSITION",
        "TRANSACTIONS",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["null", '{"deep":', '{"deep": true}'])
async def test_malformed_json_and_invalid_ids_are_rejected(env, body):
    entity_id = "invalid" if body == '{"deep": true}' else str(env.external.id)
    response = await env.client.post(
        f"/fetch/{entity_id}", data=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    env.provider.setup.assert_not_called()


@pytest.mark.asyncio
async def test_native_fetch_filters_snapshots_and_deep_history_with_real_repositories(
    env,
):
    env.entity.origin = EntityOrigin.NATIVE
    await env.entities.update(env.entity)
    accounts = EntityAccountRepository(env.db)
    account = await accounts.create(
        EntityAccount(
            id=uuid4(),
            entity_id=env.entity.id,
            created_at=datetime.now(tzlocal()),
        )
    )

    async def get_position():
        return await env.provider.global_position(None)

    async def get_transactions(_refs, _options):
        result = await env.provider.transactions(None)
        result.account = [tx for tx in result.account if tx.ref not in _refs]
        return result

    fetcher = MagicMock()
    fetcher.global_position = AsyncMock(side_effect=get_position)
    fetcher.transactions = AsyncMock(side_effect=get_transactions)
    fetcher.close = AsyncMock()
    uc = FetchFinancialDataImpl(
        position_port=env.positions,
        auto_contr_port=AsyncMock(),
        transaction_port=env.transactions,
        historic_port=AsyncMock(),
        entity_fetchers={},
        config_port=env.settings,
        credentials_port=AsyncMock(),
        sessions_port=AsyncMock(),
        last_fetches_port=AsyncMock(),
        crypto_asset_registry_port=AsyncMock(),
        crypto_asset_info_provider=AsyncMock(),
        transaction_handler_port=TransactionHandler(env.db),
        keychain_loader=AsyncMock(),
        entity_account_port=accounts,
        loan_calculator=AsyncMock(),
        real_estate_port=AsyncMock(),
        feature_flag_port=MagicMock(get_all=MagicMock(return_value={})),
        fetch_pointers_port=AsyncMock(),
        transaction_label_port=env.classifications,
        transaction_labeler=env.labeler,
    )

    async def native_fetch(deep=False):
        result = await uc.get_data(
            env.entity,
            [Feature.POSITION, Feature.TRANSACTIONS],
            fetcher,
            FetchOptions(deep=deep),
            account.id,
        )
        assert result.code == FetchResultCode.COMPLETED

    await native_fetch()
    previous = await env.transactions.get_by_entity(env.entity.id)
    included = next(tx for tx in previous.account if tx.ref == "included")
    await env.classifications.set_locked([included.id], True)
    manual = movement(env.entity, "manual", EXCLUDED_IBAN, DataSource.MANUAL)
    await env.transactions.save(Transactions(account=[manual]))
    await save_rules(env, [EXCLUDED_IBAN])
    await native_fetch()
    assert len((await env.transactions.get_by_entity(env.entity.id)).account) == 3
    current = await env.positions.get_last_grouped_by_entity()
    assert [
        entry.iban
        for entry in current[env.entity].products[ProductType.ACCOUNT].entries
    ] == ["ES999"]
    await native_fetch(deep=True)
    stored = await env.transactions.get_by_entity(env.entity.id)
    assert {tx.ref for tx in stored.account} == {"included", "manual"}
    restored = next(tx for tx in stored.account if tx.ref == "included")
    assert (await env.classifications.get_classifications_by_ids([restored.id]))[
        restored.id
    ].locked
    await save_rules(env, [EXCLUDED_IBAN, "ES999"])
    await native_fetch(deep=True)
    assert [
        tx.id for tx in (await env.transactions.get_by_entity(env.entity.id)).account
    ] == [manual.id]
    current = await env.positions.get_last_grouped_by_entity()
    assert current[env.entity].products.get(ProductType.ACCOUNT) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid",
    [
        [{"type": "IBAN", "value": "ES-invalid"}],
        [{"type": "OTHER", "value": "ES999"}],
        [{"type": "IBAN", "value": "ES999"}, {"type": "IBAN", "value": " es999 "}],
    ],
)
async def test_invalid_settings_changes_leave_saved_rules_unchanged(env, invalid):
    await save_rules(env, ["ES999"])
    response = await env.client.post(
        "/settings",
        json={
            "assets": {
                "crypto": {},
                "accounts": {"exclusions": invalid},
            }
        },
    )
    assert response.status_code == 400
    assert [
        rule.value for rule in (await env.settings.load()).assets.accounts.exclusions
    ] == ["ES999"]


@pytest.mark.asyncio
async def test_empty_json_content_type_request_keeps_default_features(env):
    response = await env.client.post(
        f"/fetch/{env.external.id}", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 200
    assert (await response.get_json())["details"]["completedFeatures"] == [
        "POSITION",
        "TRANSACTIONS",
    ]
