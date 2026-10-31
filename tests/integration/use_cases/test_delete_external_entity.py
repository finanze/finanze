import sqlite3
from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from dateutil.tz import tzlocal

from application.ports.external_entity_fetcher import ExternalEntityFetcher
from application.ports.external_integration_port import ExternalIntegrationPort
from application.use_cases.delete_external_entity import DeleteExternalEntityImpl
from domain.data_init import DatasourceInitContext
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.external_entity import (
    DeleteExternalEntityRequest,
    ExternalEntity,
    ExternalEntityStatus,
)
from domain.external_integration import ExternalIntegrationId
from domain.fetch_record import DataSource, FetchRecord
from domain.global_position import ProductType
from domain.labeling import LabelingRuleKind
from domain.transactions import AccountTx, AccountTxSelection, Transactions, TxType
from infrastructure.labeling.transaction_labeler_adapter import (
    TransactionLabelerAdapter,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.entity.entity_repository import EntitySQLRepository
from infrastructure.repository.entity.external_entity_repository import (
    ExternalEntityRepository,
)
from infrastructure.repository.fetch.last_fetches_repository import (
    LastFetchesRepository,
)
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

IBAN = "ES8814650100961754781454"


def _entity(name: str, origin: EntityOrigin) -> Entity:
    return Entity(
        id=uuid4(),
        name=name,
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=origin,
        icon_url=None,
    )


def _tx(
    entity,
    ref,
    tx_type=TxType.OUTFLOW,
    source=DataSource.REAL,
    iban=None,
    amount="150",
):
    return AccountTx(
        id=uuid4(),
        ref=ref,
        name="Traspaso Cuenta Nomina",
        amount=Dezimal(amount),
        currency="EUR",
        type=tx_type,
        date=datetime(2026, 9, 10, tzinfo=tzlocal()),
        entity=entity,
        source=source,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        iban=iban,
    )


@pytest_asyncio.fixture
async def db():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    client = DBClient(connection)
    await DatabaseUpgrader(
        client, versions, DatasourceInitContext(config=AsyncMock())
    ).upgrade()
    yield client
    connection.close()


@pytest.mark.asyncio
async def test_delete_removes_fetched_data_so_native_copy_takes_transfer(db):
    tx_repo = TransactionSQLRepository(db)
    label_repo = TransactionLabelRepository(db)
    rule_repo = LabelingRuleRepository(db)
    entity_repo = EntitySQLRepository(db)
    external_entity_repo = ExternalEntityRepository(db)
    last_fetches_repo = LastFetchesRepository(db)
    handler = TransactionHandler(db)
    labeler = TransactionLabelerAdapter(
        transaction_port=tx_repo,
        transaction_label_port=label_repo,
        labeling_rule_port=rule_repo,
        label_port=LabelRepository(db),
        config_port=AsyncMock(),
        external_integration_port=AsyncMock(),
        providers={},
        transaction_handler_port=handler,
    )

    external_bank = _entity("ING", EntityOrigin.EXTERNALLY_PROVIDED)
    native_bank = _entity("ING copy", EntityOrigin.MANUAL)
    broker = _entity("Broker", EntityOrigin.MANUAL)
    for entity in (external_bank, native_bank, broker):
        await entity_repo.insert(entity)
    external_entity = ExternalEntity(
        id=uuid4(),
        entity_id=external_bank.id,
        status=ExternalEntityStatus.LINKED,
        provider=ExternalIntegrationId.ENABLE_BANKING,
        date=datetime.now(tzlocal()),
        provider_instance_id="session-1",
    )
    await external_entity_repo.upsert(external_entity)

    external_out = _tx(external_bank, f"{IBAN}:17547814540001", iban=IBAN)
    manual_tx = _tx(external_bank, "manual-1", source=DataSource.MANUAL, amount="20")
    broker_in = _tx(broker, "broker-1", tx_type=TxType.INFLOW)
    await tx_repo.save(Transactions(account=[external_out, manual_tx, broker_in]))
    await labeler.classify(AccountTxSelection(ids=[external_out.id, broker_in.id]))
    await last_fetches_repo.save(
        [
            FetchRecord(
                entity_id=external_bank.id,
                feature=feature,
                date=datetime.now(tzlocal()),
            )
            for feature in (Feature.POSITION, Feature.TRANSACTIONS)
        ]
    )

    native_out = _tx(native_bank, "d38b57b7:0001", iban=IBAN)
    await tx_repo.save(Transactions(account=[native_out]))
    await labeler.classify(AccountTxSelection(ids=[native_out.id]))

    async def stored(tx):
        return (await tx_repo.get_account_txs(AccountTxSelection(ids=[tx.id])))[0]

    assert (await stored(native_out)).transfer_pair is None

    fetcher = AsyncMock(spec=ExternalEntityFetcher)
    integration_port = AsyncMock(spec=ExternalIntegrationPort)
    integration_port.get_payloads_by_type.return_value = {}
    await DeleteExternalEntityImpl(
        external_entity_repo,
        {ExternalIntegrationId.ENABLE_BANKING: fetcher},
        integration_port,
        tx_repo,
        last_fetches_repo,
        handler,
    ).execute(DeleteExternalEntityRequest(external_entity_id=external_entity.id))

    fetcher.unlink.assert_awaited_once_with("session-1")
    assert await external_entity_repo.get_all() == []
    assert await last_fetches_repo.get_by_entity_id(external_bank.id) == []
    remaining = await tx_repo.get_account_txs(
        AccountTxSelection(entities=[external_bank.id])
    )
    assert [tx.id for tx in remaining] == [manual_tx.id]
    assert (await stored(broker_in)).transfer_pair is None

    rules = await rule_repo.get_all()
    transfer_rule = next(r for r in rules if r.kind == LabelingRuleKind.TRANSFER)
    await labeler.apply_rule(transfer_rule)

    assert (await stored(native_out)).transfer_pair.tx_id == broker_in.id
