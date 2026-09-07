import sqlite3

import pytest

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v10.v0100_5_crypto_defi_zerion import (
    V01005CryptoDefiZerion,
)

_SCHEMA = """
CREATE TABLE crypto_currency_positions (
    id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), wallet_id CHAR(36),
    name VARCHAR(150), symbol VARCHAR(30), type VARCHAR(20), amount TEXT,
    market_value TEXT, currency CHAR(3), contract_address TEXT, crypto_asset_id CHAR(36)
);
CREATE TABLE crypto_wallets (
    id             CHAR(36)    NOT NULL PRIMARY KEY,
    entity_id      CHAR(36)    NOT NULL,
    name           TEXT        NOT NULL,
    address_source VARCHAR(20) NOT NULL,
    created_at     TIMESTAMP   NOT NULL
);
CREATE TABLE external_integrations (
    id     VARCHAR(36) NOT NULL PRIMARY KEY,
    name   VARCHAR(48) NOT NULL,
    type   VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL
);
CREATE TABLE entities (
    id         CHAR(36) PRIMARY KEY,
    name       TEXT NOT NULL,
    natural_id TEXT,
    type       VARCHAR(64) NOT NULL,
    origin     VARCHAR(32) NOT NULL
);
"""


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


async def _run_migration(conn):
    db = DBClient(conn)
    async with db.tx(skip_last_update=True) as cursor:
        await V01005CryptoDefiZerion().upgrade(
            cursor, DatasourceInitContext(config=None)
        )


@pytest.mark.asyncio
async def test_adds_crypto_defi_columns():
    conn = _conn()
    await _run_migration(conn)

    pos_cols = {
        r["name"] for r in conn.execute("PRAGMA table_info(crypto_currency_positions)")
    }
    assert {"chain", "protocol", "position_type", "icon_url"} <= pos_cols

    wallet_cols = {r["name"] for r in conn.execute("PRAGMA table_info(crypto_wallets)")}
    assert "include_wallet_tokens" in wallet_cols


@pytest.mark.asyncio
async def test_include_wallet_tokens_defaults_to_zero():
    conn = _conn()
    await _run_migration(conn)

    conn.execute(
        "INSERT INTO crypto_wallets (id, entity_id, name, address_source, created_at) "
        "VALUES ('w1', 'e1', 'W', 'MANUAL', '2026-01-01')"
    )
    row = conn.execute(
        "SELECT include_wallet_tokens FROM crypto_wallets WHERE id = 'w1'"
    ).fetchone()
    assert row["include_wallet_tokens"] == 0


@pytest.mark.asyncio
async def test_seeds_zerion_integration_and_entity():
    conn = _conn()
    await _run_migration(conn)

    integration = conn.execute(
        "SELECT id, name, type, status FROM external_integrations WHERE id = 'ZERION'"
    ).fetchone()
    assert integration is not None
    assert integration["name"] == "Zerion"
    assert integration["type"] == "CRYPTO_PROVIDER"
    assert integration["status"] == "OFF"

    entity = conn.execute(
        "SELECT * FROM entities WHERE id = 'c0000000-0000-0000-0000-000000000006'"
    ).fetchone()
    assert entity is not None
    assert entity["name"] == "Zerion"
    assert entity["type"] == "CRYPTO_WALLET"
    assert entity["origin"] == "NATIVE"
