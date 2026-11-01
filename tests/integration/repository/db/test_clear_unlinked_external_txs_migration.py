import sqlite3
from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from dateutil.tz import tzlocal

from domain.data_init import DatasourceInitContext
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.external_entity import ExternalEntity, ExternalEntityStatus
from domain.external_integration import ExternalIntegrationId
from domain.fetch_record import DataSource, FetchRecord
from domain.global_position import ProductType
from domain.transactions import AccountTx, LabelOrigin, Transactions, TxLabel, TxType
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.db.versions.v0.v11.v0110_10_clear_unlinked_external_txs import (
    V011010ClearUnlinkedExternalTxs,
)
from infrastructure.repository.entity.entity_repository import EntitySQLRepository
from infrastructure.repository.entity.external_entity_repository import (
    ExternalEntityRepository,
)
from infrastructure.repository.fetch.last_fetches_repository import (
    LastFetchesRepository,
)
from infrastructure.repository.labeling.label_repository import LabelRepository
from infrastructure.repository.labeling.transaction_label_repository import (
    TransactionLabelRepository,
)
from infrastructure.repository.transaction.transaction_repository import (
    TransactionSQLRepository,
)


def _entity(name: str, origin: EntityOrigin) -> Entity:
    return Entity(
        id=uuid4(),
        name=name,
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=origin,
        icon_url=None,
    )


def _tx(entity, tx_type=TxType.OUTFLOW, source=DataSource.REAL):
    return AccountTx(
        id=uuid4(),
        ref=str(uuid4()),
        name="Transfer",
        amount=Dezimal("100"),
        currency="EUR",
        type=tx_type,
        date=datetime(2026, 9, 10, tzinfo=tzlocal()),
        entity=entity,
        source=source,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
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
    yield client, connection
    connection.close()


@pytest.mark.asyncio
async def test_clears_fetched_data_of_unlinked_external_entities_only(db):
    client, connection = db
    entity_repo = EntitySQLRepository(client)
    tx_repo = TransactionSQLRepository(client)
    tx_label_repo = TransactionLabelRepository(client)
    last_fetches_repo = LastFetchesRepository(client)

    unlinked = _entity("ING", EntityOrigin.EXTERNALLY_PROVIDED)
    linked = _entity("Revolut", EntityOrigin.EXTERNALLY_PROVIDED)
    broker = _entity("Broker", EntityOrigin.MANUAL)
    for entity in (unlinked, linked, broker):
        await entity_repo.insert(entity)
    await ExternalEntityRepository(client).upsert(
        ExternalEntity(
            id=uuid4(),
            entity_id=linked.id,
            status=ExternalEntityStatus.UNLINKED,
            provider=ExternalIntegrationId.ENABLE_BANKING,
            date=datetime.now(tzlocal()),
        )
    )

    unlinked_real = _tx(unlinked)
    unlinked_manual = _tx(unlinked, source=DataSource.MANUAL)
    linked_real = _tx(linked)
    broker_in = _tx(broker, tx_type=TxType.INFLOW)
    await tx_repo.save(
        Transactions(account=[unlinked_real, unlinked_manual, linked_real, broker_in])
    )
    await tx_label_repo.add_transfer_pair(unlinked_real.id, broker_in.id, None)
    label = (await LabelRepository(client).get_all())[0]
    await tx_label_repo.add(
        unlinked_real.id, [TxLabel(label_id=label.id, origin=LabelOrigin.MANUAL)]
    )
    await last_fetches_repo.save(
        [
            FetchRecord(
                entity_id=entity.id,
                feature=Feature.TRANSACTIONS,
                date=datetime.now(tzlocal()),
            )
            for entity in (unlinked, linked)
        ]
    )

    async with client.tx(skip_last_update=True) as cursor:
        await V011010ClearUnlinkedExternalTxs().upgrade(
            cursor, DatasourceInitContext(config=None)
        )

    remaining = {
        row["id"] for row in connection.execute("SELECT id FROM account_transactions")
    }
    assert remaining == {
        str(unlinked_manual.id),
        str(linked_real.id),
        str(broker_in.id),
    }
    assert (
        connection.execute("SELECT COUNT(*) FROM account_transfer_pairs").fetchone()[0]
        == 0
    )
    assert (
        connection.execute(
            "SELECT COUNT(*) FROM account_transaction_labels"
        ).fetchone()[0]
        == 0
    )
    assert await last_fetches_repo.get_by_entity_id(unlinked.id) == []
    assert len(await last_fetches_repo.get_by_entity_id(linked.id)) == 1
