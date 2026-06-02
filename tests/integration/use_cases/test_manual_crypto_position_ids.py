import sqlite3
from uuid import uuid4

import pytest
import pytest_asyncio

from infrastructure.repository.db.client import DBClient
from infrastructure.repository.position.position_repository import (
    PositionSQLRepository,
)

_SCHEMA = """
    CREATE TABLE crypto_currency_positions (
        id                 CHAR(36)     NOT NULL PRIMARY KEY,
        global_position_id CHAR(36)     NOT NULL,
        wallet_id          CHAR(36),
        name               VARCHAR(150) NOT NULL,
        symbol             VARCHAR(30)  NOT NULL,
        amount             TEXT         NOT NULL,
        type               VARCHAR(20)  NOT NULL,
        market_value       TEXT,
        currency           CHAR(3),
        contract_address   TEXT,
        crypto_asset_id    CHAR(36)
    );
"""


def _insert_crypto(conn, gp_id, wallet_id=None, symbol="BTC"):
    conn.execute(
        "INSERT INTO crypto_currency_positions "
        "(id, global_position_id, wallet_id, name, symbol, amount, type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid4()),
            str(gp_id),
            str(wallet_id) if wallet_id else None,
            symbol,
            symbol,
            "1",
            "NATIVE",
        ),
    )
    conn.commit()


@pytest_asyncio.fixture
async def setup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(_SCHEMA)

    db_client = DBClient(conn)
    repository = PositionSQLRepository(client=db_client)
    yield repository, conn
    conn.close()


class TestGetManualCryptoPositionIds:
    @pytest.mark.asyncio
    async def test_returns_only_manual_positions(self, setup):
        repository, conn = setup

        manual_gp = uuid4()
        real_gp = uuid4()
        other_gp = uuid4()

        _insert_crypto(conn, manual_gp, wallet_id=None, symbol="BTC")
        _insert_crypto(conn, real_gp, wallet_id=uuid4(), symbol="ETH")

        result = await repository.get_manual_crypto_position_ids(
            [manual_gp, real_gp, other_gp]
        )

        assert result == {manual_gp}

    @pytest.mark.asyncio
    async def test_filters_by_requested_ids(self, setup):
        repository, conn = setup

        requested_gp = uuid4()
        unrequested_gp = uuid4()

        _insert_crypto(conn, requested_gp, wallet_id=None)
        _insert_crypto(conn, unrequested_gp, wallet_id=None)

        result = await repository.get_manual_crypto_position_ids([requested_gp])

        assert result == {requested_gp}

    @pytest.mark.asyncio
    async def test_deduplicates_multiple_assets_per_position(self, setup):
        repository, conn = setup

        manual_gp = uuid4()
        _insert_crypto(conn, manual_gp, wallet_id=None, symbol="BTC")
        _insert_crypto(conn, manual_gp, wallet_id=None, symbol="ETH")

        result = await repository.get_manual_crypto_position_ids([manual_gp])

        assert result == {manual_gp}

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_input(self, setup):
        repository, _ = setup

        result = await repository.get_manual_crypto_position_ids([])

        assert result == set()
