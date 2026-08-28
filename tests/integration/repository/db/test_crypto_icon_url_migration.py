import sqlite3
import pytest
from infrastructure.repository.db.client import DBClient
from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.versions.v0.v10.v0100_9_crypto_icon_url import (
    V01009CryptoIconUrl,
)

_SCHEMA = """
CREATE TABLE crypto_currency_positions (
    id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), wallet_id CHAR(36),
    name VARCHAR(150), symbol VARCHAR(30), type VARCHAR(20), amount TEXT,
    market_value TEXT, currency CHAR(3), contract_address TEXT, crypto_asset_id CHAR(36),
    chain TEXT, protocol TEXT, position_type VARCHAR(20) NOT NULL DEFAULT 'HOLDING'
);
"""


@pytest.mark.asyncio
async def test_adds_icon_url_column():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    db = DBClient(conn)
    async with db.tx(skip_last_update=True) as cur:
        await V01009CryptoIconUrl().upgrade(cur, DatasourceInitContext(config=None))
    cols = {
        r["name"] for r in conn.execute("PRAGMA table_info(crypto_currency_positions)")
    }
    assert "icon_url" in cols
