import sqlite3
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from dateutil.tz import tzlocal

from application.use_cases.create_label import CreateLabelImpl
from application.use_cases.create_labeling_rule import CreateLabelingRuleImpl
from application.use_cases.delete_label import DeleteLabelImpl
from application.use_cases.delete_labeling_rule import DeleteLabelingRuleImpl
from application.use_cases.get_cashflow_summary import GetCashflowSummaryImpl
from application.use_cases.get_labeling_rules import GetLabelingRulesImpl
from application.use_cases.get_labels import GetLabelsImpl
from application.use_cases.get_recurring_movements import GetRecurringMovementsImpl
from application.use_cases.get_transactions import GetTransactionsImpl
from application.use_cases.ignore_recurring_movement import (
    IgnoreRecurringMovementImpl,
)
from application.use_cases.preview_labeling_rule import PreviewLabelingRuleImpl
from application.use_cases.relabel_transactions import RelabelTransactionsImpl
from application.use_cases.restore_recurring_movement import (
    RestoreRecurringMovementImpl,
)
from application.use_cases.update_label import UpdateLabelImpl
from application.use_cases.update_labeling_rule import UpdateLabelingRuleImpl
from application.use_cases.update_transaction_labels import (
    UpdateTransactionLabelsImpl,
)
from domain.data_init import DatasourceInitContext
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.settings import AssetConfig, CryptoAssetConfig, Settings
from domain.transactions import AccountTx, Transactions, TxType
from infrastructure.controller.config import quart
from infrastructure.controller.exception_handler import register_exception_handlers
from infrastructure.controller.routes.cashflow_summary import cashflow_summary
from infrastructure.controller.routes.create_label import create_label
from infrastructure.controller.routes.create_labeling_rule import (
    create_labeling_rule,
)
from infrastructure.controller.routes.delete_label import delete_label
from infrastructure.controller.routes.delete_labeling_rule import (
    delete_labeling_rule,
)
from infrastructure.controller.routes.get_labeling_rules import get_labeling_rules
from infrastructure.controller.routes.get_labels import get_labels
from infrastructure.controller.routes.ignore_recurring_movement import (
    ignore_recurring_movement,
)
from infrastructure.controller.routes.preview_labeling_rule import (
    preview_labeling_rule,
)
from infrastructure.controller.routes.recurring_movements import (
    recurring_movements,
)
from infrastructure.controller.routes.relabel_transactions import (
    relabel_transactions,
)
from infrastructure.controller.routes.restore_recurring_movement import (
    restore_recurring_movement,
)
from infrastructure.controller.routes.transactions import transactions
from infrastructure.controller.routes.update_label import update_label
from infrastructure.controller.routes.update_labeling_rule import (
    update_labeling_rule,
)
from infrastructure.controller.routes.update_transaction_labels import (
    update_transaction_labels,
)
from infrastructure.labeling.transaction_labeler_adapter import (
    TransactionLabelerAdapter,
)
from infrastructure.repository.cashflow.ignored_recurring_movement_repository import (
    IgnoredRecurringMovementRepository,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.earnings_expenses.periodic_flow_repository import (
    PeriodicFlowRepository,
)
from infrastructure.repository.entity.entity_repository import EntitySQLRepository
from infrastructure.repository.labeling.label_repository import LabelRepository
from infrastructure.repository.labeling.labeling_rule_repository import (
    LabelingRuleRepository,
)
from infrastructure.repository.labeling.transaction_label_repository import (
    TransactionLabelRepository,
)
from infrastructure.repository.transaction.transaction_repository import (
    TransactionSQLRepository,
)

ENTITY = Entity(
    id=uuid4(),
    name="Bank",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.MANUAL,
    icon_url=None,
)


def _tx(name, amount, tx_type, day: date, counterparty=None):
    return AccountTx(
        id=uuid4(),
        ref=str(uuid4()),
        name=name,
        amount=Dezimal(amount),
        currency="EUR",
        type=tx_type,
        date=datetime(day.year, day.month, day.day, 12, tzinfo=tzlocal()),
        entity=ENTITY,
        source=DataSource.REAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        counterparty=counterparty,
    )


class _Ctx:
    def __init__(self, client, tx_repo, label_repo, test_client):
        self.client = client
        self.tx_repo = tx_repo
        self.label_repo = label_repo
        self.http = test_client

    async def save(self, *txs):
        await self.tx_repo.save(Transactions(account=list(txs)))

    async def label_id(self, key):
        labels = await self.label_repo.get_all()
        return str(next(label.id for label in labels if label.key == key))


@pytest_asyncio.fixture
async def ctx(tmp_path):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    client = DBClient(connection)
    await DatabaseUpgrader(
        client, versions, DatasourceInitContext(config=AsyncMock())
    ).upgrade()

    tx_repo = TransactionSQLRepository(client)
    tx_label_repo = TransactionLabelRepository(client)
    rule_repo = LabelingRuleRepository(client)
    label_repo = LabelRepository(client)
    entity_repo = EntitySQLRepository(client)
    flow_repo = PeriodicFlowRepository(client)
    ignored_repo = IgnoredRecurringMovementRepository(client)
    handler = TransactionHandler(client)
    await entity_repo.insert(ENTITY)

    config_port = AsyncMock()
    config_port.load = AsyncMock(
        return_value=Settings(
            lastUpdate=datetime.now(tzlocal()).isoformat(),
            assets=AssetConfig(crypto=CryptoAssetConfig()),
        )
    )
    exchange_rates = AsyncMock()
    exchange_rates.get = AsyncMock(return_value={"EUR": {"USD": Dezimal("1.1")}})
    enabled_entities = AsyncMock()
    enabled_entities.get_disabled_entities = AsyncMock(return_value=[])

    labeler = TransactionLabelerAdapter(
        transaction_port=tx_repo,
        transaction_label_port=tx_label_repo,
        labeling_rule_port=rule_repo,
        label_port=label_repo,
        config_port=config_port,
        external_integration_port=AsyncMock(),
        providers={},
        transaction_handler_port=handler,
    )

    get_labels_uc = GetLabelsImpl(label_repo)
    create_label_uc = CreateLabelImpl(label_repo)
    update_label_uc = UpdateLabelImpl(label_repo)
    delete_label_uc = DeleteLabelImpl(label_repo, rule_repo, handler)
    get_rules_uc = GetLabelingRulesImpl(rule_repo)
    create_rule_uc = CreateLabelingRuleImpl(rule_repo, label_repo, labeler, handler)
    update_rule_uc = UpdateLabelingRuleImpl(
        rule_repo, label_repo, tx_label_repo, labeler, handler
    )
    delete_rule_uc = DeleteLabelingRuleImpl(rule_repo, tx_label_repo, handler)
    preview_uc = PreviewLabelingRuleImpl(tx_repo)
    relabel_uc = RelabelTransactionsImpl(tx_repo, tx_label_repo, labeler, handler)
    update_tx_labels_uc = UpdateTransactionLabelsImpl(
        tx_repo, tx_label_repo, label_repo, labeler, handler
    )
    get_transactions_uc = GetTransactionsImpl(tx_repo, enabled_entities)
    cashflow_uc = GetCashflowSummaryImpl(
        tx_repo, label_repo, enabled_entities, exchange_rates
    )
    recurring_uc = GetRecurringMovementsImpl(
        tx_repo, label_repo, enabled_entities, flow_repo, exchange_rates, ignored_repo
    )
    ignore_recurring_uc = IgnoreRecurringMovementImpl(ignored_repo)
    restore_recurring_uc = RestoreRecurringMovementImpl(ignored_repo)

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    app = quart(static_dir)
    register_exception_handlers(app)

    @app.route("/api/v1/labels", methods=["GET"])
    async def get_labels_route():
        return await get_labels(get_labels_uc)

    @app.route("/api/v1/labels", methods=["POST"])
    async def create_label_route():
        return await create_label(create_label_uc)

    @app.route("/api/v1/labels/<label_id>", methods=["PUT"])
    async def update_label_route(label_id: str):
        return await update_label(update_label_uc, label_id)

    @app.route("/api/v1/labels/<label_id>", methods=["DELETE"])
    async def delete_label_route(label_id: str):
        return await delete_label(delete_label_uc, label_id)

    @app.route("/api/v1/labeling/rules", methods=["GET"])
    async def get_rules_route():
        return await get_labeling_rules(get_rules_uc)

    @app.route("/api/v1/labeling/rules", methods=["POST"])
    async def create_rule_route():
        return await create_labeling_rule(create_rule_uc)

    @app.route("/api/v1/labeling/rules/preview", methods=["POST"])
    async def preview_rule_route():
        return await preview_labeling_rule(preview_uc)

    @app.route("/api/v1/labeling/rules/<rule_id>", methods=["PUT"])
    async def update_rule_route(rule_id: str):
        return await update_labeling_rule(update_rule_uc, rule_id)

    @app.route("/api/v1/labeling/rules/<rule_id>", methods=["DELETE"])
    async def delete_rule_route(rule_id: str):
        return await delete_labeling_rule(delete_rule_uc, rule_id)

    @app.route("/api/v1/labeling/relabel", methods=["POST"])
    async def relabel_route():
        return await relabel_transactions(relabel_uc)

    @app.route("/api/v1/transactions", methods=["GET"])
    async def transactions_route():
        return await transactions(get_transactions_uc)

    @app.route("/api/v1/transactions/<tx_id>/labels", methods=["PUT"])
    async def update_tx_labels_route(tx_id: str):
        return await update_transaction_labels(update_tx_labels_uc, tx_id)

    @app.route("/api/v1/cashflow", methods=["GET"])
    async def cashflow_route():
        return await cashflow_summary(cashflow_uc)

    @app.route("/api/v1/cashflow/recurring", methods=["GET"])
    async def recurring_route():
        return await recurring_movements(recurring_uc)

    @app.route("/api/v1/cashflow/recurring/ignored", methods=["POST"])
    async def ignore_recurring_route():
        return await ignore_recurring_movement(ignore_recurring_uc)

    @app.route("/api/v1/cashflow/recurring/ignored/<ignored_id>", methods=["DELETE"])
    async def restore_recurring_route(ignored_id: str):
        return await restore_recurring_movement(restore_recurring_uc, ignored_id)

    yield _Ctx(client, tx_repo, label_repo, app.test_client())
    connection.close()


def _tx_names(payload):
    return sorted(tx["name"] for tx in payload["transactions"])


@pytest.mark.asyncio
async def test_label_crud(ctx):
    response = await ctx.http.get("/api/v1/labels")
    assert response.status_code == 200
    labels = (await response.get_json())["labels"]
    assert len(labels) == 30
    assert all(label["usage"] == 0 for label in labels)

    response = await ctx.http.post(
        "/api/v1/labels",
        json={"name": "Padel", "color": "#16a34a", "icon": "trophy"},
    )
    assert response.status_code == 201
    created = await response.get_json()
    assert created["key"] is None
    assert created["category"] == "EXPENSE"

    response = await ctx.http.put(
        f"/api/v1/labels/{created['id']}",
        json={"name": "Padel club", "category": "INCOME"},
    )
    assert response.status_code == 204
    labels = (await (await ctx.http.get("/api/v1/labels")).get_json())["labels"]
    updated = next(label for label in labels if label["id"] == created["id"])
    assert updated["name"] == "Padel club"
    assert updated["category"] == "INCOME"

    response = await ctx.http.put(
        f"/api/v1/labels/{created['id']}",
        json={"name": "Padel club", "category": "UNKNOWN"},
    )
    assert response.status_code == 400

    response = await ctx.http.delete(f"/api/v1/labels/{created['id']}")
    assert response.status_code == 204
    response = await ctx.http.delete(f"/api/v1/labels/{created['id']}")
    assert response.status_code == 404
    assert (await response.get_json())["code"] == "LABEL_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_label_requires_name(ctx):
    response = await ctx.http.post("/api/v1/labels", json={"color": "#000000"})

    assert response.status_code == 400
    assert (await response.get_json())["code"] == "INVALID_LABELING_RULE"


@pytest.mark.asyncio
async def test_rules_labels_filters_and_relabel_flow(ctx):
    day = date(2026, 3, 10)
    groceries = await ctx.label_id("groceries")
    transfer_label = await ctx.label_id("internal_transfer")
    first = _tx("MERCADONA VALENCIA", "45.20", TxType.OUTFLOW, day)
    second = _tx("Compra", "12.00", TxType.OUTFLOW, day, counterparty="Mercadona SA")
    salary = _tx("NOMINA MARZO", "2000", TxType.INFLOW, day, counterparty="ACME")
    transfer = _tx("Traspaso", "500", TxType.OUTFLOW, day)
    await ctx.save(first, second, salary, transfer)

    conditions = {"text": {"value": "mercadona", "operator": "CONTAINS"}}
    response = await ctx.http.post(
        "/api/v1/labeling/rules/preview", json={"conditions": conditions}
    )
    assert response.status_code == 200
    assert (await response.get_json())["count"] == 2

    response = await ctx.http.post(
        "/api/v1/labeling/rules",
        json={
            "name": "Supermarket",
            "conditions": conditions,
            "labels": [groceries],
            "apply_to_existing": True,
        },
    )
    assert response.status_code == 201
    saved = await response.get_json()
    assert saved["applied"] == 2
    rule_id = saved["rule"]["id"]

    rules = (await (await ctx.http.get("/api/v1/labeling/rules")).get_json())["rules"]
    assert any(rule["id"] == rule_id for rule in rules)

    response = await ctx.http.get(f"/api/v1/transactions?label={groceries}")
    payload = await response.get_json()
    assert _tx_names(payload) == ["Compra", "MERCADONA VALENCIA"]
    assert payload["transactions"][0]["labels"][0]["origin"] == "RULE"

    response = await ctx.http.get("/api/v1/transactions?unlabeled=true")
    assert _tx_names(await response.get_json()) == ["NOMINA MARZO", "Traspaso"]

    response = await ctx.http.get(f"/api/v1/transactions?exclude_label={groceries}")
    assert _tx_names(await response.get_json()) == ["NOMINA MARZO", "Traspaso"]

    response = await ctx.http.get("/api/v1/transactions?exclude_label=invalid")
    assert response.status_code == 400

    response = await ctx.http.get("/api/v1/transactions?search=acme")
    assert _tx_names(await response.get_json()) == ["NOMINA MARZO"]

    response = await ctx.http.get(
        "/api/v1/transactions?from_date=2026-03-10&to_date=2026-03-10"
    )
    assert len((await response.get_json())["transactions"]) == 4

    response = await ctx.http.put(
        f"/api/v1/transactions/{transfer.id}/labels",
        json={"labels": [transfer_label], "locked": True},
    )
    assert response.status_code == 204
    response = await ctx.http.get(f"/api/v1/transactions?label={transfer_label}")
    locked_tx = (await response.get_json())["transactions"][0]
    assert locked_tx["labels_locked"] is True
    assert locked_tx["labels"][0]["origin"] == "MANUAL"

    response = await ctx.http.post("/api/v1/labeling/relabel", json={"dry_run": True})
    assert (await response.get_json())["matched"] == 3

    response = await ctx.http.put(
        f"/api/v1/labeling/rules/{rule_id}",
        json={"conditions": conditions, "labels": [groceries], "enabled": False},
    )
    assert response.status_code == 200
    response = await ctx.http.get(f"/api/v1/transactions?label={groceries}")
    assert len((await response.get_json())["transactions"]) == 2

    response = await ctx.http.post("/api/v1/labeling/relabel", json={})
    relabeled = await response.get_json()
    assert relabeled["matched"] == 3
    assert relabeled["result"]["rule_labeled"] == 0
    response = await ctx.http.get(f"/api/v1/transactions?label={groceries}")
    assert (await response.get_json())["transactions"] == []

    response = await ctx.http.post(
        "/api/v1/labeling/relabel",
        json={"unlabeled_only": True, "dry_run": True},
    )
    assert (await response.get_json())["matched"] == 3

    response = await ctx.http.delete(f"/api/v1/labeling/rules/{rule_id}")
    assert response.status_code == 204
    response = await ctx.http.delete(f"/api/v1/labeling/rules/{rule_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_rule_and_unknown_tx(ctx):
    response = await ctx.http.post(
        "/api/v1/labeling/rules",
        json={"conditions": {"text": {"value": "x"}}, "labels": []},
    )
    assert response.status_code == 400
    assert (await response.get_json())["code"] == "INVALID_LABELING_RULE"

    response = await ctx.http.post(
        "/api/v1/labeling/rules/preview",
        json={"conditions": {"text": {"value": "(", "operator": "REGEX"}}},
    )
    assert response.status_code == 400

    response = await ctx.http.put(
        f"/api/v1/transactions/{uuid4()}/labels", json={"labels": []}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_transfer_rule_crud(ctx):
    transfer_label = await ctx.label_id("internal_transfer")

    response = await ctx.http.post(
        "/api/v1/labeling/rules",
        json={
            "kind": "TRANSFER",
            "conditions": {"max_days": 2, "min_amount": "100"},
            "labels": [transfer_label],
            "apply_to_existing": True,
        },
    )
    assert response.status_code == 201
    saved = await response.get_json()
    assert saved["rule"]["kind"] == "TRANSFER"
    assert saved["rule"]["conditions"]["max_days"] == 2
    rule_id = saved["rule"]["id"]

    response = await ctx.http.put(
        f"/api/v1/labeling/rules/{rule_id}",
        json={
            "kind": "MATCH",
            "conditions": {"max_days": 5},
            "labels": [transfer_label],
        },
    )
    assert response.status_code == 200
    rules = (await (await ctx.http.get("/api/v1/labeling/rules")).get_json())["rules"]
    updated = next(rule for rule in rules if rule["id"] == rule_id)
    assert updated["kind"] == "TRANSFER"
    assert updated["conditions"]["max_days"] == 5

    response = await ctx.http.post(
        "/api/v1/labeling/rules",
        json={
            "kind": "TRANSFER",
            "conditions": {"text": {"value": "x"}},
            "labels": [transfer_label],
        },
    )
    assert response.status_code == 400
    assert (await response.get_json())["code"] == "INVALID_LABELING_RULE"

    tx = _tx("Wire", "500", TxType.OUTFLOW, date(2026, 3, 10))
    await ctx.save(tx)
    response = await ctx.http.get("/api/v1/transactions")
    assert (await response.get_json())["transactions"][0]["transfer_pair"] is None


@pytest.mark.asyncio
async def test_rule_iban_condition_is_normalized_and_validated(ctx):
    groceries = await ctx.label_id("groceries")

    response = await ctx.http.post(
        "/api/v1/labeling/rules",
        json={
            "conditions": {"ibans": ["es76 0000 0000 0000 01", "ES7600000000000001"]},
            "labels": [groceries],
        },
    )
    assert response.status_code == 201
    saved = await response.get_json()
    assert saved["rule"]["conditions"]["ibans"] == ["ES7600000000000001"]

    response = await ctx.http.post(
        "/api/v1/labeling/rules",
        json={"conditions": {"ibans": ["ES76-0001"]}, "labels": [groceries]},
    )
    assert response.status_code == 400
    assert (await response.get_json())["code"] == "INVALID_LABELING_RULE"


@pytest.mark.asyncio
async def test_cashflow_summary_excludes_transfers(ctx):
    groceries = await ctx.label_id("groceries")
    transfer_label = await ctx.label_id("internal_transfer")
    purchase = _tx("MERCADONA", "100", TxType.OUTFLOW, date(2026, 3, 5))
    salary = _tx("NOMINA", "2000", TxType.INFLOW, date(2026, 3, 1))
    transfer = _tx("Traspaso", "500", TxType.OUTFLOW, date(2026, 3, 6))
    previous = _tx("NOMINA", "1800", TxType.INFLOW, date(2026, 2, 1))
    await ctx.save(purchase, salary, transfer, previous)
    await ctx.http.put(
        f"/api/v1/transactions/{purchase.id}/labels", json={"labels": [groceries]}
    )
    await ctx.http.put(
        f"/api/v1/transactions/{transfer.id}/labels",
        json={"labels": [transfer_label]},
    )

    response = await ctx.http.get(
        "/api/v1/cashflow?currency=eur&from_date=2026-03-01&to_date=2026-03-31"
    )
    assert response.status_code == 200
    summary = await response.get_json()
    assert summary["currency"] == "EUR"
    assert summary["totals"]["income"] == 2000
    assert summary["totals"]["expenses"] == 100
    assert summary["totals"]["net"] == 1900
    assert summary["excluded_count"] == 1
    assert summary["previous"]["income"] == 1800
    assert [point["period"] for point in summary["series"]] == ["2026-03-01"]
    by_label = {row["label_id"]: row for row in summary["by_label"]}
    assert by_label[groceries]["expenses"] == 100
    assert by_label[None]["income"] == 2000


@pytest.mark.asyncio
async def test_cashflow_validation(ctx):
    response = await ctx.http.get(
        "/api/v1/cashflow?from_date=2026-03-01&to_date=2026-03-31"
    )
    assert response.status_code == 400

    response = await ctx.http.get(
        "/api/v1/cashflow?currency=EUR&from_date=2026-03-31&to_date=2026-03-01"
    )
    assert response.status_code == 400

    response = await ctx.http.get("/api/v1/cashflow/recurring?currency=EUR&type=FEE")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_recurring_movements(ctx):
    today = datetime.now(tzlocal()).date()
    await ctx.save(
        *[
            _tx("NETFLIX.COM", "12.99", TxType.OUTFLOW, today - timedelta(days=30 * i))
            for i in range(4)
        ],
        _tx("Random shop", "30", TxType.OUTFLOW, today - timedelta(days=3)),
    )

    response = await ctx.http.get("/api/v1/cashflow/recurring?currency=EUR")

    assert response.status_code == 200
    movements = (await response.get_json())["movements"]
    assert len(movements) == 1
    assert movements[0]["key"] == "netflix com"
    assert movements[0]["frequency"] == "MONTHLY"
    assert movements[0]["occurrences"] == 4
    assert movements[0]["tracked_flow_id"] is None
    assert movements[0]["ignored_id"] is None


@pytest.mark.asyncio
async def test_ignore_and_restore_recurring_movement(ctx):
    today = datetime.now(tzlocal()).date()
    await ctx.save(
        *[
            _tx("NETFLIX.COM", "12.99", TxType.OUTFLOW, today - timedelta(days=30 * i))
            for i in range(4)
        ]
    )

    response = await ctx.http.post(
        "/api/v1/cashflow/recurring/ignored",
        json={
            "key": "netflix com",
            "type": "OUTFLOW",
            "currency": "eur",
            "amount": 12.99,
        },
    )
    assert response.status_code == 201
    ignored = await response.get_json()
    assert ignored["currency"] == "EUR"

    response = await ctx.http.get("/api/v1/cashflow/recurring?currency=EUR")
    movements = (await response.get_json())["movements"]
    assert movements[0]["ignored_id"] == ignored["id"]

    response = await ctx.http.delete(
        f"/api/v1/cashflow/recurring/ignored/{ignored['id']}"
    )
    assert response.status_code == 204

    response = await ctx.http.get("/api/v1/cashflow/recurring?currency=EUR")
    movements = (await response.get_json())["movements"]
    assert movements[0]["ignored_id"] is None


@pytest.mark.asyncio
async def test_ignore_recurring_movement_validation(ctx):
    for body in [
        {"key": "", "type": "OUTFLOW", "currency": "EUR", "amount": 10},
        {"key": "netflix", "type": "FEE", "currency": "EUR", "amount": 10},
        {"key": "netflix", "type": "OUTFLOW", "currency": "EUR", "amount": 0},
        {"key": "netflix", "type": "OUTFLOW", "currency": "EUR"},
    ]:
        response = await ctx.http.post("/api/v1/cashflow/recurring/ignored", json=body)
        assert response.status_code == 400

    response = await ctx.http.delete("/api/v1/cashflow/recurring/ignored/not-a-uuid")
    assert response.status_code == 400
