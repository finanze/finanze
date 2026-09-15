import sqlite3

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v10.v0100_4_crypto_etp_to_crypto_positions import (
    V01004CryptoEtpToCryptoPositions,
)

SCHEMA = """
CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE stock_positions (
    id CHAR(36) PRIMARY KEY,
    global_position_id CHAR(36),
    name TEXT NOT NULL,
    ticker VARCHAR(16) NOT NULL,
    isin VARCHAR(12) NOT NULL,
    market VARCHAR(50) NOT NULL,
    shares TEXT NOT NULL,
    initial_investment TEXT NOT NULL,
    average_buy_price TEXT NOT NULL,
    market_value TEXT NOT NULL,
    currency CHAR(3) NOT NULL,
    type VARCHAR(32) NOT NULL,
    subtype VARCHAR(32)
);
CREATE TABLE crypto_currency_positions (
    id CHAR(36) NOT NULL PRIMARY KEY,
    global_position_id CHAR(36) NOT NULL,
    wallet_id CHAR(36),
    name VARCHAR(150) NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    amount TEXT NOT NULL,
    type VARCHAR(20) NOT NULL,
    market_value TEXT,
    currency CHAR(3),
    contract_address TEXT,
    crypto_asset_id CHAR(36)
);
CREATE TABLE crypto_currency_initial_investments (
    id CHAR(36) PRIMARY KEY,
    crypto_currency_position CHAR(36) NOT NULL,
    currency CHAR(3) NOT NULL,
    initial_investment TEXT NOT NULL,
    average_buy_price TEXT NOT NULL
);
CREATE TABLE crypto_assets (
    id CHAR(36) PRIMARY KEY,
    name TEXT,
    symbol TEXT
);
"""


def _stock_row(connection, row_id, isin="XF000BTC0017", subtype="CRYPTO", gp="gp-1"):
    connection.execute(
        "INSERT INTO stock_positions VALUES (?, ?, 'Bitcoin', 'BTC', ?, 'BHS', "
        "'0.012215', '1000.9277', '81942.5066', '982.0147', 'EUR', 'ETF', ?)",
        (row_id, gp, isin, subtype),
    )


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    connection.execute(
        "INSERT INTO crypto_assets VALUES ('asset-btc', 'Bitcoin', 'BTC')"
    )
    client = DBClient(connection)
    yield client, connection
    connection.close()


async def _run(client):
    async with client.tx() as cursor:
        await V01004CryptoEtpToCryptoPositions().upgrade(
            cursor, DatasourceInitContext(config=None)
        )


@pytest.mark.asyncio
async def test_moves_crypto_etp_position_preserving_data(setup):
    client, connection = setup
    _stock_row(connection, "pos-1")
    connection.commit()

    await _run(client)

    position = connection.execute("SELECT * FROM crypto_currency_positions").fetchone()
    assert position["id"] == "pos-1"
    assert position["global_position_id"] == "gp-1"
    assert position["name"] == "Bitcoin"
    assert position["symbol"] == "BTC"
    assert position["amount"] == "0.012215"
    assert position["type"] == "NATIVE"
    assert position["market_value"] == "982.0147"
    assert position["currency"] == "EUR"
    assert position["wallet_id"] is None
    assert position["contract_address"] is None
    assert position["crypto_asset_id"] == "asset-btc"

    investment = connection.execute(
        "SELECT * FROM crypto_currency_initial_investments"
    ).fetchone()
    assert investment["crypto_currency_position"] == "pos-1"
    assert investment["currency"] == "EUR"
    assert investment["initial_investment"] == "1000.9277"
    assert investment["average_buy_price"] == "81942.5066"
    assert len(investment["id"]) == 36

    assert (
        connection.execute("SELECT COUNT(*) c FROM stock_positions").fetchone()["c"]
        == 0
    )


@pytest.mark.asyncio
async def test_leaves_other_stock_positions_untouched(setup):
    client, connection = setup
    _stock_row(connection, "pos-etf", isin="IE0003UVYC20", subtype="FUND")
    _stock_row(connection, "pos-gold", isin="DE000A2T0VU5", subtype="ETCS")
    connection.commit()

    await _run(client)

    remaining = {
        row["id"] for row in connection.execute("SELECT id FROM stock_positions")
    }
    assert remaining == {"pos-etf", "pos-gold"}
    assert (
        connection.execute(
            "SELECT COUNT(*) c FROM crypto_currency_positions"
        ).fetchone()["c"]
        == 0
    )


@pytest.mark.asyncio
async def test_does_not_duplicate_when_crypto_position_already_exists(setup):
    client, connection = setup
    _stock_row(connection, "pos-1")
    connection.execute(
        "INSERT INTO crypto_currency_positions VALUES ('existing', 'gp-1', NULL, "
        "'Bitcoin', 'BTC', '0.012215', 'NATIVE', '982.0147', 'EUR', NULL, 'asset-btc')"
    )
    connection.commit()

    await _run(client)

    ids = {
        row["id"]
        for row in connection.execute("SELECT id FROM crypto_currency_positions")
    }
    assert ids == {"existing"}
    assert (
        connection.execute("SELECT COUNT(*) c FROM stock_positions").fetchone()["c"]
        == 1
    )


@pytest.mark.asyncio
async def test_is_idempotent(setup):
    client, connection = setup
    _stock_row(connection, "pos-1")
    connection.commit()

    await _run(client)
    await _run(client)

    assert (
        connection.execute(
            "SELECT COUNT(*) c FROM crypto_currency_positions"
        ).fetchone()["c"]
        == 1
    )
    assert (
        connection.execute(
            "SELECT COUNT(*) c FROM crypto_currency_initial_investments"
        ).fetchone()["c"]
        == 1
    )
