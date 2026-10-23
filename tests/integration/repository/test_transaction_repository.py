import sqlite3
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from dateutil.tz import tzlocal
from pydantic import ValidationError

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.transactions import (
    AccountTx,
    StockTx,
    TransactionQueryRequest,
    Transactions,
    TxType,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.transaction.transaction_repository import (
    TransactionSQLRepository,
)


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)")
    connection.execute(
        "CREATE TABLE entity_accounts (id CHAR(36) PRIMARY KEY, deleted_at TIMESTAMP)"
    )
    connection.execute(
        """
        CREATE TABLE entities (
            id CHAR(36) PRIMARY KEY,
            name TEXT,
            natural_id TEXT,
            type TEXT,
            origin TEXT,
            icon_url TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE investment_transactions (
            id CHAR(36) PRIMARY KEY,
            ref TEXT NOT NULL,
            name TEXT NOT NULL,
            amount TEXT NOT NULL,
            currency CHAR(3) NOT NULL,
            type VARCHAR(32) NOT NULL,
            date DATETIME NOT NULL,
            entity_id CHAR(36) NOT NULL,
            is_real BOOLEAN NOT NULL,
            source TEXT NOT NULL,
            product_type VARCHAR(32),
            created_at DATETIME NOT NULL,
            isin TEXT,
            ticker TEXT,
            market TEXT,
            shares TEXT,
            price TEXT,
            net_amount TEXT,
            fees TEXT,
            retentions TEXT,
            order_date DATETIME,
            linked_tx TEXT,
            interests TEXT,
            iban TEXT,
            portfolio_name TEXT,
            product_subtype TEXT,
            asset_contract_address TEXT,
            entity_account_id CHAR(36),
            split_ratio TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE account_transactions (
            id CHAR(36) PRIMARY KEY,
            ref TEXT NOT NULL,
            name TEXT NOT NULL,
            amount TEXT NOT NULL,
            currency CHAR(3) NOT NULL,
            type VARCHAR(32) NOT NULL,
            date DATETIME NOT NULL,
            entity_id CHAR(36) NOT NULL,
            is_real BOOLEAN NOT NULL,
            source TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            fees TEXT,
            retentions TEXT,
            interest_rate TEXT,
            avg_balance TEXT,
            net_amount TEXT,
            entity_account_id CHAR(36),
            counterparty TEXT,
            iban TEXT,
            linked_tx TEXT,
            labels_locked BOOLEAN NOT NULL DEFAULT FALSE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE account_transaction_labels (
            tx_id CHAR(36) NOT NULL,
            label_id CHAR(36) NOT NULL,
            origin VARCHAR(16) NOT NULL,
            rule_id CHAR(36),
            provider TEXT,
            confidence TEXT,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (tx_id, label_id)
        )
        """
    )
    connection.execute(
        "CREATE TABLE account_transfer_pairs "
        "(tx_id CHAR(36) PRIMARY KEY, paired_tx_id CHAR(36), rule_id CHAR(36))"
    )
    connection.commit()
    yield TransactionSQLRepository(DBClient(connection)), connection
    connection.close()


@pytest.mark.asyncio
async def test_stock_split_ratio_and_null_shares_roundtrip(setup):
    repository, connection = setup
    entity = Entity(
        id=uuid4(),
        name="Broker",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )
    connection.execute(
        "INSERT INTO entities (id, name, natural_id, type, origin, icon_url) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            str(entity.id),
            entity.name,
            entity.natural_id,
            entity.type.value,
            entity.origin.value,
            entity.icon_url,
        ),
    )
    connection.commit()
    transaction = StockTx(
        id=uuid4(),
        ref="split-1",
        name="ACME 2-for-1 split",
        amount=Dezimal(0),
        currency="USD",
        type=TxType.SPLIT,
        date=datetime(2025, 6, 1, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.STOCK_ETF,
        isin="US0000000001",
        ticker="ACME",
        shares=None,
        price=Dezimal(0),
        fees=Dezimal(0),
        retentions=Dezimal(0),
        split_ratio=Dezimal("2"),
    )

    await repository.save(Transactions(investment=[transaction]))
    loaded = await repository.get_by_id(transaction.id)

    assert isinstance(loaded, StockTx)
    assert loaded.type == TxType.SPLIT
    assert loaded.shares is None
    assert loaded.split_ratio == Dezimal("2")

    filtered = await repository.get_by_filters(TransactionQueryRequest())

    assert len(filtered) == 1
    assert isinstance(filtered[0], StockTx)
    assert filtered[0].split_ratio == Dezimal("2")


@pytest_asyncio.fixture
async def sortable_transactions(setup):
    repository, connection = setup
    entity = Entity(
        id=uuid4(),
        name="Bank and broker",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )
    connection.execute(
        "INSERT INTO entities (id, name, type, origin) VALUES (?, ?, ?, ?)",
        (str(entity.id), entity.name, entity.type.value, entity.origin.value),
    )
    connection.commit()
    account_txs = []
    investment_txs = []
    for index, amount in enumerate(["10", "-2.25", "100.25", "0", "2.5", "-10.5"]):
        common = {
            "id": uuid4(),
            "ref": f"tx-{index}",
            "name": f"Transaction {index}",
            "amount": Dezimal(amount),
            "currency": "EUR",
            "date": datetime(2026, 1, index + 1, tzinfo=tzlocal()),
            "entity": entity,
            "source": DataSource.MANUAL,
            "fees": Dezimal(0),
            "retentions": Dezimal(0),
        }
        if index % 2:
            account_txs.append(
                AccountTx(
                    **common, type=TxType.OUTFLOW, product_type=ProductType.ACCOUNT
                )
            )
        else:
            investment_txs.append(
                StockTx(
                    **common,
                    type=TxType.BUY,
                    product_type=ProductType.STOCK_ETF,
                    shares=Dezimal(1),
                    price=Dezimal(amount),
                )
            )
    await repository.save(Transactions(investment=investment_txs, account=account_txs))
    return repository


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("options", "expected_indices"),
    [
        ({}, [5, 4, 3, 2, 1, 0]),
        ({"sort_by": "date", "sort_order": "desc"}, [5, 4, 3, 2, 1, 0]),
        ({"sort_by": "date", "sort_order": "asc"}, [0, 1, 2, 3, 4, 5]),
        ({"sort_by": "amount"}, [2, 0, 4, 3, 1, 5]),
        ({"sort_by": "amount", "sort_order": "desc"}, [2, 0, 4, 3, 1, 5]),
        ({"sort_by": "amount", "sort_order": "asc"}, [5, 1, 3, 4, 0, 2]),
        ({"page": 2, "limit": 2}, [3, 2]),
        ({"sort_order": "asc", "page": 2, "limit": 2}, [2, 3]),
        ({"sort_by": "amount", "page": 2, "limit": 2}, [4, 3]),
        ({"sort_by": "amount", "sort_order": "asc", "page": 2, "limit": 2}, [3, 4]),
        (
            {"sort_by": "amount", "types": [TxType.BUY], "limit": 2},
            [2, 0],
        ),
    ],
)
async def test_get_by_filters_sorts_before_pagination(
    sortable_transactions, options, expected_indices
):
    transactions = await sortable_transactions.get_by_filters(
        TransactionQueryRequest(**options)
    )

    assert [tx.ref for tx in transactions] == [
        f"tx-{index}" for index in expected_indices
    ]


@pytest.mark.parametrize(
    "options",
    [
        {"sort_by": "name"},
        {"sort_by": "amount; DROP TABLE account_transactions"},
        {"sort_order": "ascending"},
        {"sort_order": "desc; DROP TABLE account_transactions"},
    ],
)
def test_transaction_query_rejects_invalid_sorting(options):
    with pytest.raises(ValidationError):
        TransactionQueryRequest(**options)
