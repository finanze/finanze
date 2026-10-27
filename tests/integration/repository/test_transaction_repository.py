import sqlite3
from dataclasses import replace
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
    DepositTx,
    FundTx,
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


@pytest_asyncio.fixture
async def searchable_transactions(setup):
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
    common = {
        "amount": Dezimal("100"),
        "currency": "EUR",
        "date": datetime(2026, 1, 1, tzinfo=tzlocal()),
        "entity": entity,
        "source": DataSource.MANUAL,
        "fees": Dezimal(0),
        "retentions": Dezimal(0),
    }
    stock = StockTx(
        **common,
        id=uuid4(),
        ref="stock",
        name="Technology stock",
        type=TxType.BUY,
        product_type=ProductType.STOCK_ETF,
        isin="US0378331005",
        price=Dezimal("100"),
    )
    fund = FundTx(
        **common,
        id=uuid4(),
        ref="fund",
        name="Global fund",
        type=TxType.BUY,
        product_type=ProductType.FUND,
        isin="IE00B4L5Y983",
        price=Dezimal("100"),
        net_amount=Dezimal("100"),
    )
    account = AccountTx(
        **common,
        id=uuid4(),
        ref="account",
        name="Card payment",
        type=TxType.OUTFLOW,
        product_type=ProductType.ACCOUNT,
        counterparty="Merchant Ltd",
    )
    await repository.save(Transactions(investment=[stock, fund], account=[account]))
    return repository, connection


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("search", "product_types", "expected_refs"),
    [
        ("us0378331005", None, ["stock"]),
        ("  us0378331005  ", [], ["stock"]),
        ("378331", [ProductType.STOCK_ETF], ["stock"]),
        ("us0378", [ProductType.ACCOUNT, ProductType.STOCK_ETF], ["stock"]),
        ("ie00b4l5y983", None, ["fund"]),
        ("b4l5y", [ProductType.FUND], ["fund"]),
        ("b4l5y", [ProductType.STOCK_ETF, ProductType.FUND], ["fund"]),
        ("us0378", [ProductType.ACCOUNT], []),
        ("ie00b4l5y983", [ProductType.STOCK_ETF], []),
        ("global", [ProductType.FUND], ["fund"]),
        ("merchant", [ProductType.ACCOUNT], ["account"]),
    ],
)
async def test_get_by_filters_searches_investment_isins(
    searchable_transactions, search, product_types, expected_refs
):
    repository, _ = searchable_transactions
    transactions = await repository.get_by_filters(
        TransactionQueryRequest(search=search, product_types=product_types)
    )

    assert [transaction.ref for transaction in transactions] == expected_refs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("product_types", "unlabeled", "searches_isin"),
    [
        (None, False, True),
        ([], False, True),
        ([ProductType.STOCK_ETF], False, True),
        ([ProductType.FUND], False, True),
        ([ProductType.ACCOUNT, ProductType.FUND], False, True),
        ([ProductType.ACCOUNT], False, False),
        ([ProductType.DEPOSIT], False, False),
        ([ProductType.ACCOUNT, ProductType.CRYPTO], False, False),
        (None, True, False),
        ([ProductType.FUND], True, False),
    ],
)
async def test_get_by_filters_only_searches_isin_when_eligible(
    searchable_transactions, product_types, unlabeled, searches_isin
):
    repository, connection = searchable_transactions
    statements = []
    connection.set_trace_callback(statements.append)
    try:
        await repository.get_by_filters(
            TransactionQueryRequest(
                search="unmatched", product_types=product_types, unlabeled=unlabeled
            )
        )
    finally:
        connection.set_trace_callback(None)

    search_statement = next(
        statement for statement in statements if "tx.counterparty LIKE" in statement
    )
    assert ("tx.isin LIKE" in search_statement) is searches_isin


@pytest.mark.asyncio
async def test_isin_search_respects_other_filters_and_pagination(
    searchable_transactions,
):
    repository, connection = searchable_transactions
    stock = (
        await repository.get_by_filters(TransactionQueryRequest(search="technology"))
    )[0]
    other_entity = replace(stock.entity, id=uuid4(), name="Other broker")
    connection.execute(
        "INSERT INTO entities (id, name, type, origin) VALUES (?, ?, ?, ?)",
        (
            str(other_entity.id),
            other_entity.name,
            other_entity.type.value,
            other_entity.origin.value,
        ),
    )
    connection.commit()
    other_stock = replace(
        stock,
        id=uuid4(),
        ref="other-stock",
        name=f"Sale {stock.isin}",
        type=TxType.SELL,
        date=datetime(2026, 1, 2, tzinfo=tzlocal()),
        entity=other_entity,
        source=DataSource.REAL,
    )
    await repository.save(Transactions(investment=[other_stock]))

    async def refs(**filters):
        transactions = await repository.get_by_filters(
            TransactionQueryRequest(search=stock.isin, **filters)
        )
        return [transaction.ref for transaction in transactions]

    assert await refs() == ["other-stock", "stock"]
    assert await refs(page=1, limit=1) == ["other-stock"]
    assert await refs(page=2, limit=1) == ["stock"]
    assert await refs(page=3, limit=1) == []
    assert await refs(entities=[other_entity.id]) == ["other-stock"]
    assert await refs(excluded_entities=[other_entity.id]) == ["stock"]
    assert await refs(types=[TxType.SELL]) == ["other-stock"]
    assert await refs(from_date=other_stock.date) == ["other-stock"]


@pytest.mark.asyncio
async def test_isin_search_escapes_wildcards_and_handles_missing_isin(
    searchable_transactions,
):
    repository, _ = searchable_transactions
    stock = (
        await repository.get_by_filters(TransactionQueryRequest(search="technology"))
    )[0]
    literal = replace(stock, id=uuid4(), ref="literal", isin="US%_\\TEST")
    decoy = replace(stock, id=uuid4(), ref="decoy", isin="USABXTEST")
    missing = replace(
        stock, id=uuid4(), ref="missing", name="Missing ISIN asset", isin=None
    )
    await repository.save(Transactions(investment=[literal, decoy, missing]))

    literal_matches = await repository.get_by_filters(
        TransactionQueryRequest(search="%_\\")
    )
    name_matches = await repository.get_by_filters(
        TransactionQueryRequest(search="missing isin")
    )

    assert [transaction.ref for transaction in literal_matches] == ["literal"]
    assert [transaction.ref for transaction in name_matches] == ["missing"]


@pytest.mark.asyncio
async def test_isin_search_does_not_match_other_investment_products(
    searchable_transactions,
):
    repository, connection = searchable_transactions
    stock = (
        await repository.get_by_filters(TransactionQueryRequest(search="technology"))
    )[0]
    deposit = DepositTx(
        id=uuid4(),
        ref="deposit",
        name="Deposit",
        amount=stock.amount,
        currency=stock.currency,
        type=TxType.INTEREST,
        date=stock.date,
        entity=stock.entity,
        source=stock.source,
        product_type=ProductType.DEPOSIT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        net_amount=stock.amount,
    )
    await repository.save(Transactions(investment=[deposit]))
    connection.execute(
        "UPDATE investment_transactions SET isin = ? WHERE id = ?",
        (stock.isin, str(deposit.id)),
    )
    connection.commit()

    transactions = await repository.get_by_filters(
        TransactionQueryRequest(search=stock.isin)
    )

    assert [transaction.ref for transaction in transactions] == ["stock"]


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
