import json
import sqlite3
from datetime import date, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from dateutil.tz import tzlocal

from application.ports.external_tx_labeling_provider import (
    ExternalTxLabelingProvider,
)
from application.use_cases.create_labeling_rule import CreateLabelingRuleImpl
from application.use_cases.delete_labeling_rule import DeleteLabelingRuleImpl
from application.use_cases.relabel_transactions import RelabelTransactionsImpl
from application.use_cases.update_transaction_labels import (
    UpdateTransactionLabelsImpl,
)
from domain.data_init import DatasourceInitContext
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.external_integration import ExternalIntegrationId
from domain.external_labeling import ExternalLabelSuggestion
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.labeling import (
    LabelCategory,
    LabelingRule,
    LabelingRuleConditions,
    LabelingRuleKind,
    LabelingTrigger,
    RelabelRequest,
    SaveLabelingRuleRequest,
    TextCondition,
    UpdateTransactionLabelsRequest,
)
from domain.settings import (
    AssetConfig,
    CryptoAssetConfig,
    ExternalLabelingConfig,
    ExternalLabelingExamplesConfig,
    LabelingConfig,
    Settings,
)
from domain.transactions import (
    AccountTx,
    AccountTxSelection,
    FundTx,
    LabelOrigin,
    TransactionQueryRequest,
    Transactions,
    TxLabel,
    TxType,
)
from infrastructure.client.ai.openai.openai_client import OpenAIClient
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.labeling.ai_labeling_presets import LABELING_PRESETS
from infrastructure.labeling.ai_labeling_provider import AILabelingProvider
from infrastructure.labeling.transaction_labeler_adapter import (
    TransactionLabelerAdapter,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
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


def _settings(external: ExternalLabelingConfig) -> Settings:
    return Settings(
        lastUpdate=datetime.now(tzlocal()).isoformat(),
        assets=AssetConfig(crypto=CryptoAssetConfig()),
        labeling=LabelingConfig(external=external),
    )


class _Env:
    def __init__(self, connection, client):
        self.connection = connection
        self.client = client
        self.tx_repo = TransactionSQLRepository(client)
        self.tx_label_repo = TransactionLabelRepository(client)
        self.rule_repo = LabelingRuleRepository(client)
        self.label_repo = LabelRepository(client)
        self.entity_repo = EntitySQLRepository(client)
        self.handler = TransactionHandler(client)
        self.config_port = AsyncMock()
        self.config_port.load = AsyncMock(
            return_value=_settings(ExternalLabelingConfig())
        )
        self.integration_port = AsyncMock()
        self.integration_port.get_payload = AsyncMock(return_value={"api_key": "k"})
        self.provider = AsyncMock(spec=ExternalTxLabelingProvider)
        self.provider.label = AsyncMock(return_value=[])
        self.labeler = TransactionLabelerAdapter(
            transaction_port=self.tx_repo,
            transaction_label_port=self.tx_label_repo,
            labeling_rule_port=self.rule_repo,
            label_port=self.label_repo,
            config_port=self.config_port,
            external_integration_port=self.integration_port,
            providers={ExternalIntegrationId.OPENROUTER: self.provider},
            transaction_handler_port=self.handler,
        )
        self.entity = Entity(
            id=uuid4(),
            name="Bank",
            natural_id=None,
            type=EntityType.FINANCIAL_INSTITUTION,
            origin=EntityOrigin.MANUAL,
            icon_url=None,
        )
        self.broker = Entity(
            id=uuid4(),
            name="Broker",
            natural_id=None,
            type=EntityType.FINANCIAL_INSTITUTION,
            origin=EntityOrigin.MANUAL,
            icon_url=None,
        )

    async def label_id(self, key: str):
        labels = await self.label_repo.get_all()
        return next(label.id for label in labels if label.key == key)

    def account_tx(self, name, amount, tx_type=TxType.OUTFLOW, day=10, **kwargs):
        return AccountTx(
            id=uuid4(),
            ref=kwargs.pop("ref", str(uuid4())),
            name=name,
            amount=Dezimal(amount),
            currency="EUR",
            type=tx_type,
            date=datetime(2025, 3, day, 12, tzinfo=tzlocal()),
            entity=kwargs.pop("entity", self.entity),
            source=DataSource.MANUAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal(0),
            retentions=Dezimal(0),
            **kwargs,
        )

    async def save(self, *txs):
        await self.tx_repo.save(Transactions(account=list(txs)))

    async def labels_of(self, tx_id):
        return (await self.tx_label_repo.get_by_tx_ids([tx_id])).get(tx_id, [])

    async def account_tx_by_id(self, tx_id):
        return (await self.tx_repo.get_account_txs(AccountTxSelection(ids=[tx_id])))[0]


@pytest_asyncio.fixture
async def env():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    client = DBClient(connection)
    await DatabaseUpgrader(
        client, versions, DatasourceInitContext(config=AsyncMock())
    ).upgrade()
    environment = _Env(connection, client)
    await environment.entity_repo.insert(environment.entity)
    await environment.entity_repo.insert(environment.broker)
    yield environment
    connection.close()


async def _create_rule(
    env, conditions, label_ids, apply_to_existing=False, kind=LabelingRuleKind.MATCH
):
    uc = CreateLabelingRuleImpl(env.rule_repo, env.label_repo, env.labeler, env.handler)
    return await uc.execute(
        SaveLabelingRuleRequest(
            rule=LabelingRule(
                id=None, conditions=conditions, label_ids=label_ids, kind=kind
            ),
            apply_to_existing=apply_to_existing,
        )
    )


async def _transfer_rule(env):
    rules = await env.rule_repo.get_all()
    return next(rule for rule in rules if rule.kind == LabelingRuleKind.TRANSFER)


@pytest.mark.asyncio
async def test_migration_seeds_base_labels_and_default_rules(env):
    labels = await env.label_repo.get_all()
    assert len(labels) == 30
    excluded = {
        label.key for label in labels if label.category == LabelCategory.EXCLUDED
    }
    assert excluded == {"internal_transfer", "savings_investment"}
    income = {label.key for label in labels if label.category == LabelCategory.INCOME}
    assert "interest" in income

    rules = await env.rule_repo.get_all()
    match_rules = [rule for rule in rules if rule.kind == LabelingRuleKind.MATCH]
    assert {tuple(rule.conditions.types) for rule in match_rules} == {
        (TxType.INTEREST,),
        (TxType.FEE,),
    }

    transfer_rules = [rule for rule in rules if rule.kind == LabelingRuleKind.TRANSFER]
    assert len(transfer_rules) == 1
    assert transfer_rules[0].enabled
    assert transfer_rules[0].conditions.max_days == 3
    assert transfer_rules[0].label_ids == [await env.label_id("internal_transfer")]


@pytest.mark.asyncio
async def test_classify_applies_matching_rules_and_default_interest_rule(env):
    groceries = await env.label_id("groceries")
    await _create_rule(
        env,
        LabelingRuleConditions(text=TextCondition(value="Mercadóna")),
        [groceries],
    )
    purchase = env.account_tx("MERCADONA VALENCIA", "45.20")
    interest = env.account_tx("Interest", "3.10", tx_type=TxType.INTEREST)
    other = env.account_tx("Cinema", "12")
    await env.save(purchase, interest, other)

    result = await env.labeler.classify(
        AccountTxSelection(ids=[purchase.id, interest.id, other.id])
    )

    assert result.rule_labeled == 2
    purchase_labels = await env.labels_of(purchase.id)
    assert [label.label_id for label in purchase_labels] == [groceries]
    assert purchase_labels[0].origin == LabelOrigin.RULE
    assert [label.label_id for label in await env.labels_of(interest.id)] == [
        await env.label_id("interest")
    ]
    assert await env.labels_of(other.id) == []


@pytest.mark.asyncio
async def test_classify_skips_locked_transactions(env):
    groceries = await env.label_id("groceries")
    await _create_rule(
        env, LabelingRuleConditions(text=TextCondition(value="market")), [groceries]
    )
    tx = env.account_tx("Market", "10", labels_locked=True)
    await env.save(tx)

    result = await env.labeler.classify(AccountTxSelection(ids=[tx.id]))

    assert result.skipped_locked == 1
    assert await env.labels_of(tx.id) == []


@pytest.mark.asyncio
async def test_classify_links_investment_settlement(env):
    fund_buy = FundTx(
        id=uuid4(),
        ref="FUND-1",
        name="Buy fund",
        amount=Dezimal("995"),
        net_amount=Dezimal("1000"),
        currency="EUR",
        type=TxType.BUY,
        date=datetime(2025, 3, 9, 10, tzinfo=tzlocal()),
        entity=env.entity,
        source=DataSource.MANUAL,
        product_type=ProductType.FUND,
        isin="LU0000000001",
        shares=Dezimal("10"),
        price=Dezimal("99.5"),
        fees=Dezimal("5"),
    )
    await env.tx_repo.save(Transactions(investment=[fund_buy]))
    cash_leg = env.account_tx("Fund subscription", "1000")
    unrelated = env.account_tx("Other", "1000", day=25)
    await env.save(cash_leg, unrelated)

    result = await env.labeler.classify(
        AccountTxSelection(ids=[cash_leg.id, unrelated.id])
    )

    assert result.linked == 1
    assert (await env.account_tx_by_id(cash_leg.id)).linked_tx == "FUND-1"
    assert (await env.account_tx_by_id(unrelated.id)).linked_tx is None


@pytest.mark.asyncio
async def test_create_rule_apply_to_existing_and_delete_rule_removes_labels(env):
    subscriptions = await env.label_id("subscriptions")
    netflix = env.account_tx("NETFLIX.COM", "12.99")
    locked = env.account_tx("NETFLIX.COM", "12.99", labels_locked=True)
    await env.save(netflix, locked)

    saved = await _create_rule(
        env,
        LabelingRuleConditions(
            text=TextCondition(value="netflix"), types=[TxType.OUTFLOW]
        ),
        [subscriptions],
        apply_to_existing=True,
    )

    assert saved.applied == 1
    assert [label.label_id for label in await env.labels_of(netflix.id)] == [
        subscriptions
    ]
    assert await env.labels_of(locked.id) == []

    await DeleteLabelingRuleImpl(env.rule_repo, env.tx_label_repo, env.handler).execute(
        saved.rule.id
    )
    assert await env.labels_of(netflix.id) == []


@pytest.mark.asyncio
async def test_update_transaction_labels_locks_and_unlock_reapplies_rules(env):
    groceries = await env.label_id("groceries")
    leisure = await env.label_id("leisure")
    await _create_rule(
        env, LabelingRuleConditions(text=TextCondition(value="lidl")), [groceries]
    )
    tx = env.account_tx("LIDL", "30")
    await env.save(tx)
    await env.labeler.classify(AccountTxSelection(ids=[tx.id]))

    uc = UpdateTransactionLabelsImpl(
        env.tx_repo, env.tx_label_repo, env.label_repo, env.labeler, env.handler
    )
    await uc.execute(UpdateTransactionLabelsRequest(tx_id=tx.id, label_ids=[leisure]))

    stored = await env.account_tx_by_id(tx.id)
    assert stored.labels_locked is True
    assert [(label.label_id, label.origin) for label in stored.labels] == [
        (leisure, LabelOrigin.MANUAL)
    ]

    await uc.execute(
        UpdateTransactionLabelsRequest(tx_id=tx.id, label_ids=[], locked=False)
    )
    stored = await env.account_tx_by_id(tx.id)
    assert stored.labels_locked is False
    assert [(label.label_id, label.origin) for label in stored.labels] == [
        (groceries, LabelOrigin.RULE)
    ]


@pytest.mark.asyncio
async def test_relabel_filters_by_labels_and_dry_run(env):
    groceries = await env.label_id("groceries")
    shopping = await env.label_id("shopping")
    first = env.account_tx("Shop A", "10", day=5)
    second = env.account_tx("Shop B", "20", day=20)
    await env.save(first, second)
    await env.tx_label_repo.add(
        first.id,
        [TxLabel(label_id=shopping, origin=LabelOrigin.RULE)],
    )
    await _create_rule(
        env, LabelingRuleConditions(text=TextCondition(value="shop")), [groceries]
    )

    uc = RelabelTransactionsImpl(
        env.tx_repo, env.tx_label_repo, env.labeler, env.handler
    )
    dry = await uc.execute(RelabelRequest(with_labels=[shopping], dry_run=True))
    assert dry.matched == 1
    assert dry.result is None

    result = await uc.execute(
        RelabelRequest(from_date=date(2025, 3, 1), to_date=date(2025, 3, 10))
    )
    assert result.matched == 1
    assert [label.label_id for label in await env.labels_of(first.id)] == [groceries]
    assert await env.labels_of(second.id) == []


@pytest.mark.asyncio
async def test_classify_external_stores_confident_suggestions(env):
    restaurants = await env.label_id("restaurants")
    groceries = await env.label_id("groceries")
    env.config_port.load = AsyncMock(
        return_value=_settings(
            ExternalLabelingConfig(
                enabled=True,
                provider="OPENROUTER",
                model="~typesafe/jev-latest",
                minConfidence=70,
                examples=ExternalLabelingExamplesConfig(enabled=True, count=5),
                instructions="  Burgers are restaurants  ",
            )
        )
    )
    confident = env.account_tx("Burger place", "15")
    unsure = env.account_tx("Something", "9")
    manual = env.account_tx("Corner shop", "4", labels_locked=True)
    await env.save(confident, unsure, manual)
    await env.tx_label_repo.add(
        manual.id,
        [TxLabel(label_id=groceries, origin=LabelOrigin.MANUAL)],
    )
    env.provider.label = AsyncMock(
        return_value=[
            ExternalLabelSuggestion(
                tx_id=confident.id, label_id=restaurants, confidence=Dezimal("0.91")
            ),
            ExternalLabelSuggestion(
                tx_id=unsure.id, label_id=restaurants, confidence=Dezimal("0.40")
            ),
        ]
    )

    result = await env.labeler.classify_external(
        AccountTxSelection(ids=[confident.id, unsure.id, manual.id]),
        LabelingTrigger.AUTO,
    )

    assert result.external_labeled == 1
    stored = await env.labels_of(confident.id)
    assert stored[0].origin == LabelOrigin.EXTERNAL
    assert stored[0].confidence == Dezimal("0.91")
    assert stored[0].provider == "OPENROUTER:~typesafe/jev-latest"
    assert await env.labels_of(unsure.id) == []

    request = env.provider.label.await_args[0][0]
    assert {tx.id for tx in request.txs} == {confident.id, unsure.id}
    assert [example.label_ids for example in request.examples] == [[groceries]]
    assert request.instructions == "Burgers are restaurants"
    assert request.upstream_provider is None


@pytest.mark.asyncio
async def test_classify_external_passes_upstream_provider(env):
    env.config_port.load = AsyncMock(
        return_value=_external_config(upstreamProvider="  openai/flex  ")
    )
    env.provider.label = AsyncMock(return_value=[])
    tx = env.account_tx("Burger place", "15")
    await env.save(tx)

    await env.labeler.classify_external(
        AccountTxSelection(ids=[tx.id]), LabelingTrigger.MANUAL
    )

    request = env.provider.label.await_args[0][0]
    assert request.upstream_provider == "openai/flex"


@pytest.mark.asyncio
async def test_classify_external_examples_only_from_selected_origins(env):
    groceries = await env.label_id("groceries")
    restaurants = await env.label_id("restaurants")
    manual = env.account_tx("Corner shop", "4", labels_locked=True)
    ruled = env.account_tx("Pizza", "12", labels_locked=True)
    pending = env.account_tx("Burger place", "15")
    await env.save(manual, ruled, pending)
    await env.tx_label_repo.add(
        manual.id, [TxLabel(label_id=groceries, origin=LabelOrigin.MANUAL)]
    )
    await env.tx_label_repo.add(
        ruled.id, [TxLabel(label_id=restaurants, origin=LabelOrigin.RULE)]
    )
    env.provider.label = AsyncMock(return_value=[])

    async def examples_for(origins):
        env.config_port.load = AsyncMock(
            return_value=_settings(
                ExternalLabelingConfig(
                    enabled=True,
                    provider="OPENROUTER",
                    model="m/x",
                    examples=ExternalLabelingExamplesConfig(
                        enabled=True, count=5, origins=origins
                    ),
                )
            )
        )
        await env.labeler.classify_external(
            AccountTxSelection(ids=[pending.id]),
            LabelingTrigger.MANUAL,
            retry_unmatched=True,
        )
        request = env.provider.label.await_args[0][0]
        return [example.label_ids for example in request.examples or []]

    assert await examples_for([LabelOrigin.MANUAL]) == [[groceries]]
    assert await examples_for([LabelOrigin.RULE]) == [[restaurants]]
    assert await examples_for([LabelOrigin.EXTERNAL]) == []


@pytest.mark.asyncio
async def test_classify_external_disabled_or_auto_run_off_does_nothing(env):
    tx = env.account_tx("Burger place", "15")
    await env.save(tx)

    await env.labeler.classify_external(
        AccountTxSelection(ids=[tx.id]), LabelingTrigger.AUTO
    )
    env.config_port.load = AsyncMock(
        return_value=_settings(
            ExternalLabelingConfig(
                enabled=True, provider="OPENROUTER", model="m/x", autoRun=False
            )
        )
    )
    await env.labeler.classify_external(
        AccountTxSelection(ids=[tx.id]), LabelingTrigger.AUTO
    )

    env.provider.label.assert_not_awaited()


@pytest.mark.asyncio
async def test_classify_external_errors_are_swallowed(env):
    env.config_port.load = AsyncMock(
        return_value=_settings(
            ExternalLabelingConfig(enabled=True, provider="OPENROUTER", model="m/x")
        )
    )
    env.provider.label = AsyncMock(side_effect=RuntimeError("boom"))
    tx = env.account_tx("Burger place", "15")
    await env.save(tx)

    result = await env.labeler.classify_external(
        AccountTxSelection(ids=[tx.id]), LabelingTrigger.MANUAL
    )

    assert result.external_error == "RuntimeError"
    assert result.external_error_details is None
    assert await env.labels_of(tx.id) == []

    env.provider.label = AsyncMock(return_value=[])
    await env.labeler.classify_external(
        AccountTxSelection(ids=[tx.id]), LabelingTrigger.MANUAL
    )
    env.provider.label.assert_awaited_once()


def _openai_session(category: str) -> AsyncMock:
    async def request(method, url, **kwargs):
        if method == "GET":
            return HttpResponse(
                httpx.Response(200, json={"id": "gpt-6-luna", "object": "model"})
            )
        movements = json.loads(kwargs["json"]["input"][0]["content"])
        results = [
            {"id": movement_id, "category": category, "confidence": 0.95}
            for movement_id in movements
        ]
        output_text = {"type": "output_text", "text": json.dumps({"results": results})}
        return HttpResponse(
            httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [{"type": "message", "content": [output_text]}],
                },
            )
        )

    session = AsyncMock()
    session.request.side_effect = request
    return session


@pytest.mark.asyncio
async def test_migration_seeds_openai_integration(env):
    row = env.connection.execute(
        "SELECT name, type, status FROM external_integrations WHERE id = 'OPENAI'"
    ).fetchone()
    assert (row["name"], row["type"], row["status"]) == (
        "OpenAI",
        "AI_PROVIDER",
        "OFF",
    )


@pytest.mark.asyncio
async def test_classify_external_with_openai_provider(env):
    restaurants = await env.label_id("restaurants")
    client = OpenAIClient()
    client._session = _openai_session("restaurants")
    labeler = TransactionLabelerAdapter(
        transaction_port=env.tx_repo,
        transaction_label_port=env.tx_label_repo,
        labeling_rule_port=env.rule_repo,
        label_port=env.label_repo,
        config_port=env.config_port,
        external_integration_port=env.integration_port,
        providers={
            ExternalIntegrationId.OPENAI: AILabelingProvider(
                client, LABELING_PRESETS[ExternalIntegrationId.OPENAI]
            )
        },
        transaction_handler_port=env.handler,
    )
    env.config_port.load = AsyncMock(
        return_value=_settings(
            ExternalLabelingConfig(enabled=True, provider="OPENAI", model="gpt-6-luna")
        )
    )
    tx = env.account_tx("Burger place", "15")
    await env.save(tx)

    result = await labeler.classify_external(
        AccountTxSelection(ids=[tx.id]), LabelingTrigger.MANUAL
    )

    assert result.external_labeled == 1
    stored = await env.labels_of(tx.id)
    assert stored[0].label_id == restaurants
    assert stored[0].origin == LabelOrigin.EXTERNAL
    assert stored[0].confidence == Dezimal("0.95")
    assert stored[0].provider == "OPENAI:gpt-6-luna"

    method, url = client._session.request.call_args_list[-1].args
    body = client._session.request.call_args_list[-1].kwargs["json"]
    assert (method, url) == ("POST", "https://api.openai.com/v1/responses")
    assert body["model"] == "gpt-6-luna"
    assert body["store"] is False
    assert body["reasoning"] == {"effort": "none"}
    assert body["text"]["format"]["strict"] is True
    assert "temperature" not in body


@pytest.mark.asyncio
async def test_relabel_reports_openai_quota_error_details(env):
    client = OpenAIClient()
    client._session = AsyncMock()
    client._session.request.side_effect = [
        HttpResponse(httpx.Response(200, json={"id": "gpt-6-luna"})),
        HttpResponse(
            httpx.Response(
                429,
                json={
                    "error": {
                        "message": "You exceeded your current quota",
                        "type": "insufficient_quota",
                        "code": "insufficient_quota",
                    }
                },
            )
        ),
    ]
    labeler = TransactionLabelerAdapter(
        transaction_port=env.tx_repo,
        transaction_label_port=env.tx_label_repo,
        labeling_rule_port=env.rule_repo,
        label_port=env.label_repo,
        config_port=env.config_port,
        external_integration_port=env.integration_port,
        providers={
            ExternalIntegrationId.OPENAI: AILabelingProvider(
                client, LABELING_PRESETS[ExternalIntegrationId.OPENAI]
            )
        },
        transaction_handler_port=env.handler,
    )
    env.config_port.load = AsyncMock(
        return_value=_settings(
            ExternalLabelingConfig(enabled=True, provider="OPENAI", model="gpt-6-luna")
        )
    )
    tx = env.account_tx("Burger place", "15")
    await env.save(tx)

    result = await RelabelTransactionsImpl(
        env.tx_repo, env.tx_label_repo, labeler, env.handler
    ).execute(RelabelRequest(include_external=True))

    assert result.external.external_error == "ExternalLabelingUnavailable"
    assert result.external.external_error_details == "Insufficient OpenAI quota"
    assert await env.labels_of(tx.id) == []


def _external_config(**kwargs) -> Settings:
    return _settings(
        ExternalLabelingConfig(
            enabled=True, provider="OPENROUTER", model="m/x", **kwargs
        )
    )


async def _unmatched_at(env, tx_id):
    classification = (await env.tx_label_repo.get_classifications_by_ids([tx_id])).get(
        tx_id
    )
    return classification.external_unmatched_at if classification else None


@pytest.mark.asyncio
async def test_classify_external_skips_previously_unmatched_unless_retry(env):
    restaurants = await env.label_id("restaurants")
    env.config_port.load = AsyncMock(return_value=_external_config())
    matched = env.account_tx("Burger place", "15")
    unmatched = env.account_tx("Something", "9")
    await env.save(matched, unmatched)
    env.provider.label = AsyncMock(
        return_value=[
            ExternalLabelSuggestion(
                tx_id=matched.id, label_id=restaurants, confidence=Dezimal("0.9")
            )
        ]
    )
    selection = AccountTxSelection(ids=[matched.id, unmatched.id])

    await env.labeler.classify_external(selection, LabelingTrigger.MANUAL)

    assert await _unmatched_at(env, unmatched.id) is not None
    assert await _unmatched_at(env, matched.id) is None

    env.provider.label = AsyncMock(return_value=[])
    result = await env.labeler.classify_external(selection, LabelingTrigger.MANUAL)
    assert result.processed == 0
    env.provider.label.assert_not_awaited()

    env.provider.label = AsyncMock(
        return_value=[
            ExternalLabelSuggestion(
                tx_id=unmatched.id, label_id=restaurants, confidence=Dezimal("0.8")
            )
        ]
    )
    result = await env.labeler.classify_external(
        selection, LabelingTrigger.MANUAL, retry_unmatched=True
    )
    request = env.provider.label.await_args[0][0]
    assert [tx.id for tx in request.txs] == [unmatched.id]
    assert result.external_labeled == 1
    assert await _unmatched_at(env, unmatched.id) is None


@pytest.mark.asyncio
async def test_relabel_external_advances_through_history_without_resending(env):
    env.config_port.load = AsyncMock(return_value=_external_config(maxPerRun=2))
    oldest = env.account_tx("Old", "1", day=5)
    middle = env.account_tx("Mid", "2", day=10)
    newest = env.account_tx("New", "3", day=15)
    await env.save(oldest, middle, newest)
    uc = RelabelTransactionsImpl(
        env.tx_repo, env.tx_label_repo, env.labeler, env.handler
    )

    async def sent_ids(**kwargs):
        env.provider.label = AsyncMock(return_value=[])
        await uc.execute(RelabelRequest(include_external=True, **kwargs))
        if not env.provider.label.await_count:
            return set()
        return {tx.id for tx in env.provider.label.await_args[0][0].txs}

    assert await sent_ids() == {newest.id, middle.id}
    assert await sent_ids() == {oldest.id}
    assert await sent_ids() == set()
    assert await sent_ids(retry_external_unmatched=True) == {newest.id, middle.id}


@pytest.mark.asyncio
async def test_unmatched_marker_survives_reinsert(env):
    tx = env.account_tx("Something", "9", ref="REF-U")
    await env.save(tx)
    await env.tx_label_repo.set_external_unmatched(
        [tx.id], datetime(2025, 3, 20, tzinfo=tzlocal())
    )

    snapshot = await env.tx_label_repo.get_classifications_by_source(DataSource.MANUAL)
    await env.tx_repo.delete_by_id(tx.id)
    reinserted = env.account_tx("Something", "9", ref="REF-U")
    await env.save(reinserted)
    await env.tx_label_repo.restore({reinserted.id: snapshot[(env.entity.id, "REF-U")]})

    assert await _unmatched_at(env, reinserted.id) == datetime(
        2025, 3, 20, tzinfo=tzlocal()
    )
    assert (
        await env.tx_repo.get_account_txs(
            AccountTxSelection(ids=[reinserted.id], exclude_external_unmatched=True)
        )
        == []
    )


@pytest.mark.asyncio
async def test_get_by_filters_supports_label_unlabeled_and_search(env):
    groceries = await env.label_id("groceries")
    labeled = env.account_tx("Mercadona", "10", counterparty="Mercadona SA")
    unlabeled = env.account_tx("Gym 100%_club", "30")
    await env.save(labeled, unlabeled)
    await env.tx_label_repo.add(
        labeled.id,
        [TxLabel(label_id=groceries, origin=LabelOrigin.MANUAL)],
    )

    by_label = await env.tx_repo.get_by_filters(
        TransactionQueryRequest(labels=[groceries])
    )
    assert [tx.id for tx in by_label] == [labeled.id]
    assert by_label[0].labels[0].label_id == groceries
    assert by_label[0].counterparty == "Mercadona SA"

    only_unlabeled = await env.tx_repo.get_by_filters(
        TransactionQueryRequest(unlabeled=True)
    )
    assert [tx.id for tx in only_unlabeled] == [unlabeled.id]

    without_groceries = await env.tx_repo.get_by_filters(
        TransactionQueryRequest(excluded_labels=[groceries])
    )
    assert [tx.id for tx in without_groceries] == [unlabeled.id]

    searched = await env.tx_repo.get_by_filters(TransactionQueryRequest(search="100%_"))
    assert [tx.id for tx in searched] == [unlabeled.id]


@pytest.mark.asyncio
async def test_classification_snapshot_restores_after_reinsert(env):
    groceries = await env.label_id("groceries")
    tx = env.account_tx("Market", "10", ref="REF-1", labels_locked=True)
    await env.save(tx)
    await env.tx_label_repo.add(
        tx.id,
        [TxLabel(label_id=groceries, origin=LabelOrigin.MANUAL)],
    )

    snapshot = await env.tx_label_repo.get_classifications_by_source(DataSource.MANUAL)
    await env.tx_repo.delete_by_id(tx.id)
    reinserted = env.account_tx("Market", "10", ref="REF-1")
    await env.save(reinserted)
    await env.tx_label_repo.restore({reinserted.id: snapshot[(env.entity.id, "REF-1")]})

    stored = await env.account_tx_by_id(reinserted.id)
    assert stored.labels_locked is True
    assert [label.label_id for label in stored.labels] == [groceries]


def _label_pairs(labels):
    return [(label.label_id, label.origin, label.rule_id) for label in labels]


@pytest.mark.asyncio
async def test_classify_pairs_pass_through_chain_with_existing_outflow(env):
    external_out = env.account_tx("Transfer to B100", "1500", day=10)
    await env.save(external_out)
    await env.labeler.classify(AccountTxSelection(ids=[external_out.id]))

    main_iban = "ES7600000000000000000001"
    main_in = env.account_tx(
        "MARCOS ALVAREZ VIDAL",
        "1500",
        tx_type=TxType.INFLOW,
        entity=env.broker,
        iban=main_iban,
    )
    main_out = env.account_tx(
        "AHORRO PARA HUCHA PRINCIPAL", "1500", entity=env.broker, iban=main_iban
    )
    savings_in = env.account_tx(
        "AHORRO PARA HUCHA PRINCIPAL",
        "1500",
        tx_type=TxType.INFLOW,
        entity=env.broker,
        iban="ES7600000000000000000002",
    )
    await env.save(main_in, main_out, savings_in)

    result = await env.labeler.classify(
        AccountTxSelection(ids=[main_in.id, main_out.id, savings_in.id])
    )

    assert result.paired == 2
    assert (await env.account_tx_by_id(external_out.id)).transfer_pair.tx_id == (
        main_in.id
    )
    assert (await env.account_tx_by_id(main_out.id)).transfer_pair.tx_id == (
        savings_in.id
    )


@pytest.mark.asyncio
async def test_classify_pairs_transfers_between_entities(env):
    transfer_label = await env.label_id("internal_transfer")
    other_income = await env.label_id("other_income")
    rule = await _transfer_rule(env)
    await _create_rule(
        env,
        LabelingRuleConditions(text=TextCondition(value="transfer")),
        [other_income],
    )
    outflow = env.account_tx("Transfer to broker", "500", day=10)
    inflow = env.account_tx(
        "Incoming transfer", "500", tx_type=TxType.INFLOW, day=12, entity=env.broker
    )
    far = env.account_tx(
        "Incoming transfer", "500", tx_type=TxType.INFLOW, day=20, entity=env.broker
    )
    same_entity = env.account_tx(
        "Incoming transfer", "500", tx_type=TxType.INFLOW, day=10
    )
    other_amount = env.account_tx(
        "Incoming transfer", "499", tx_type=TxType.INFLOW, day=10, entity=env.broker
    )
    await env.save(outflow, inflow, far, same_entity, other_amount)

    result = await env.labeler.classify(
        AccountTxSelection(
            ids=[tx.id for tx in (outflow, inflow, far, same_entity, other_amount)]
        )
    )

    assert result.paired == 1
    stored_out = await env.account_tx_by_id(outflow.id)
    stored_in = await env.account_tx_by_id(inflow.id)
    assert stored_out.transfer_pair.tx_id == inflow.id
    assert stored_out.transfer_pair.entity_id == env.broker.id
    assert stored_out.transfer_pair.rule_id == rule.id
    assert stored_in.transfer_pair.tx_id == outflow.id
    expected = [(transfer_label, LabelOrigin.RULE, rule.id)]
    assert _label_pairs(stored_out.labels) == expected
    assert _label_pairs(stored_in.labels) == expected
    for tx in (far, same_entity, other_amount):
        stored = await env.account_tx_by_id(tx.id)
        assert stored.transfer_pair is None
        assert [label.label_id for label in stored.labels] == [other_income]


@pytest.mark.asyncio
async def test_classify_pairs_new_tx_with_existing_partner(env):
    transfer_label = await env.label_id("internal_transfer")
    groceries = await env.label_id("groceries")
    outflow = env.account_tx("Wire", "250", day=10)
    await env.save(outflow)
    await env.labeler.classify(AccountTxSelection(ids=[outflow.id]))
    await env.tx_label_repo.add(
        outflow.id, [TxLabel(label_id=groceries, origin=LabelOrigin.EXTERNAL)]
    )

    inflow = env.account_tx(
        "Deposit", "250", tx_type=TxType.INFLOW, day=9, entity=env.broker
    )
    await env.save(inflow)
    result = await env.labeler.classify(AccountTxSelection(ids=[inflow.id]))

    assert result.paired == 1
    stored_out = await env.account_tx_by_id(outflow.id)
    assert stored_out.transfer_pair.tx_id == inflow.id
    assert [(label.label_id, label.origin) for label in stored_out.labels] == [
        (transfer_label, LabelOrigin.RULE)
    ]


@pytest.mark.asyncio
async def test_disabled_transfer_rule_and_custom_filters(env):
    transfer_label = await env.label_id("internal_transfer")
    savings = await env.label_id("savings_investment")
    default_rule = await _transfer_rule(env)
    default_rule.enabled = False
    await env.rule_repo.update(default_rule)

    big_out = env.account_tx("Wire", "1000", day=10)
    big_in = env.account_tx(
        "Deposit", "1000", tx_type=TxType.INFLOW, day=11, entity=env.broker
    )
    small_out = env.account_tx("Wire", "50", day=10)
    small_in = env.account_tx(
        "Deposit", "50", tx_type=TxType.INFLOW, day=10, entity=env.broker
    )
    late_out = env.account_tx("Wire", "300", day=1)
    late_in = env.account_tx(
        "Deposit", "300", tx_type=TxType.INFLOW, day=3, entity=env.broker
    )
    txs = [big_out, big_in, small_out, small_in, late_out, late_in]
    await env.save(*txs)

    result = await env.labeler.classify(AccountTxSelection(ids=[tx.id for tx in txs]))
    assert result.paired == 0

    saved = await _create_rule(
        env,
        LabelingRuleConditions(
            min_amount=Dezimal(100),
            entities=[env.entity.id, env.broker.id],
            max_days=1,
        ),
        [savings],
        apply_to_existing=True,
        kind=LabelingRuleKind.TRANSFER,
    )

    assert saved.applied == 2
    stored_out = await env.account_tx_by_id(big_out.id)
    assert stored_out.transfer_pair.tx_id == big_in.id
    assert [label.label_id for label in stored_out.labels] == [savings]
    for tx in (small_out, small_in, late_out, late_in):
        stored = await env.account_tx_by_id(tx.id)
        assert stored.transfer_pair is None
        assert transfer_label not in [label.label_id for label in stored.labels]


@pytest.mark.asyncio
async def test_unpair_locks_tx_and_clears_partner(env):
    outflow = env.account_tx("Wire", "500", day=10)
    inflow = env.account_tx(
        "Deposit", "500", tx_type=TxType.INFLOW, day=10, entity=env.broker
    )
    await env.save(outflow, inflow)
    await env.labeler.classify(AccountTxSelection(ids=[outflow.id, inflow.id]))

    uc = UpdateTransactionLabelsImpl(
        env.tx_repo, env.tx_label_repo, env.label_repo, env.labeler, env.handler
    )
    await uc.execute(
        UpdateTransactionLabelsRequest(
            tx_id=outflow.id, label_ids=[], locked=False, unpair=True
        )
    )

    stored_out = await env.account_tx_by_id(outflow.id)
    stored_in = await env.account_tx_by_id(inflow.id)
    assert stored_out.labels_locked is True
    assert stored_out.transfer_pair is None
    assert stored_out.labels == []
    assert stored_in.transfer_pair is None
    assert stored_in.labels == []

    result = await env.labeler.classify(AccountTxSelection(ids=[inflow.id]))
    assert result.paired == 0


@pytest.mark.asyncio
async def test_deleted_partner_clears_stale_transfer_label(env):
    outflow = env.account_tx("Wire", "500", day=10)
    inflow = env.account_tx(
        "Deposit", "500", tx_type=TxType.INFLOW, day=10, entity=env.broker
    )
    await env.save(outflow, inflow)
    await env.labeler.classify(AccountTxSelection(ids=[outflow.id, inflow.id]))

    await env.tx_repo.delete_by_id(inflow.id)
    stored = await env.account_tx_by_id(outflow.id)
    assert stored.transfer_pair is None
    assert len(stored.labels) == 1

    unrelated = env.account_tx("Coffee", "3", day=15)
    await env.save(unrelated)
    await env.labeler.classify(AccountTxSelection(ids=[unrelated.id]))

    assert await env.labels_of(outflow.id) == []


@pytest.mark.asyncio
async def test_classification_snapshot_restores_transfer_pair(env):
    outflow = env.account_tx("Wire", "500", day=10, ref="OUT-1")
    inflow = env.account_tx(
        "Deposit", "500", tx_type=TxType.INFLOW, day=10, entity=env.broker
    )
    await env.save(outflow, inflow)
    await env.labeler.classify(AccountTxSelection(ids=[outflow.id, inflow.id]))

    snapshot = await env.tx_label_repo.get_classifications_by_ids([outflow.id])
    await env.tx_repo.delete_by_id(outflow.id)
    reinserted = env.account_tx("Wire", "500", day=10, ref="OUT-1")
    await env.save(reinserted)
    await env.tx_label_repo.restore({reinserted.id: snapshot[outflow.id]})

    stored_out = await env.account_tx_by_id(reinserted.id)
    stored_in = await env.account_tx_by_id(inflow.id)
    assert stored_out.transfer_pair.tx_id == inflow.id
    assert stored_in.transfer_pair.tx_id == reinserted.id
    assert len(stored_out.labels) == 1


@pytest.mark.asyncio
async def test_delete_transfer_rule_removes_pairs_and_labels(env):
    rule = await _transfer_rule(env)
    outflow = env.account_tx("Wire", "500", day=10)
    inflow = env.account_tx(
        "Deposit", "500", tx_type=TxType.INFLOW, day=10, entity=env.broker
    )
    await env.save(outflow, inflow)
    await env.labeler.classify(AccountTxSelection(ids=[outflow.id, inflow.id]))

    await DeleteLabelingRuleImpl(env.rule_repo, env.tx_label_repo, env.handler).execute(
        rule.id
    )

    for tx in (outflow, inflow):
        stored = await env.account_tx_by_id(tx.id)
        assert stored.transfer_pair is None
        assert stored.labels == []


CHECKING = "ES7600000000000000000001"
SAVINGS = "ES7600000000000000000002"


@pytest.mark.asyncio
async def test_classify_pairs_same_entity_accounts_and_persists_iban(env):
    transfer_label = await env.label_id("internal_transfer")
    outflow = env.account_tx("AHORRO", "50", day=10, iban=CHECKING)
    inflow = env.account_tx("AHORRO", "50", tx_type=TxType.INFLOW, day=10, iban=SAVINGS)
    refund = env.account_tx(
        "Refund", "50", tx_type=TxType.INFLOW, day=10, iban=CHECKING
    )
    await env.save(outflow, inflow, refund)

    result = await env.labeler.classify(
        AccountTxSelection(ids=[outflow.id, inflow.id, refund.id])
    )

    assert result.paired == 1
    stored_out = await env.account_tx_by_id(outflow.id)
    assert stored_out.iban == CHECKING
    assert stored_out.transfer_pair.tx_id == inflow.id
    assert [label.label_id for label in stored_out.labels] == [transfer_label]
    assert (await env.account_tx_by_id(refund.id)).transfer_pair is None

    filtered = await env.tx_repo.get_by_filters(TransactionQueryRequest(limit=50))
    assert {tx.id: tx.iban for tx in filtered} == {
        outflow.id: CHECKING,
        inflow.id: SAVINGS,
        refund.id: CHECKING,
    }


@pytest.mark.asyncio
async def test_rule_with_iban_condition_only_labels_that_account(env):
    groceries = await env.label_id("groceries")
    checking = env.account_tx("Market", "20", day=10, iban=CHECKING)
    savings = env.account_tx("Market", "20", day=11, iban=SAVINGS)
    unknown = env.account_tx("Market", "20", day=12)
    await env.save(checking, savings, unknown)

    saved = await _create_rule(
        env,
        LabelingRuleConditions(text=TextCondition(value="market"), ibans=[CHECKING]),
        [groceries],
        apply_to_existing=True,
    )

    assert saved.applied == 1
    assert saved.rule.conditions.ibans == [CHECKING]
    stored_rule = await env.rule_repo.get_by_id(saved.rule.id)
    assert stored_rule.conditions.ibans == [CHECKING]
    assert [label.label_id for label in await env.labels_of(checking.id)] == [groceries]
    assert await env.labels_of(savings.id) == []
    assert await env.labels_of(unknown.id) == []
