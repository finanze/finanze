import sqlite3
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from dateutil.tz import tzlocal

from domain.crypto import CryptoCurrencyType, CryptoPositionType
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import (
    CryptoCurrencies,
    CryptoCurrencyPosition,
    CryptoCurrencyWallet,
    GlobalPosition,
    ProductType,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.position.position_repository import (
    PositionSQLRepository,
)

# Minimal schema covering only the tables touched by saving/loading a
# wallet-less (manual/DeFi) crypto position: global_positions (for the
# GlobalPosition row), crypto_currency_positions (with the new DeFi
# columns), and the two tables LEFT JOINed by the crypto SELECT.
_SCHEMA = """
    CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT);

    CREATE TABLE global_positions (
        id CHAR(36) PRIMARY KEY,
        entity_id CHAR(36) NOT NULL,
        date DATETIME NOT NULL,
        source VARCHAR(255) NOT NULL,
        entity_account_id CHAR(36)
    );

    CREATE TABLE crypto_currency_positions (
        id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), wallet_id CHAR(36),
        name VARCHAR(150), symbol VARCHAR(30), type VARCHAR(20), amount TEXT,
        market_value TEXT, currency CHAR(3), contract_address TEXT, crypto_asset_id CHAR(36),
        chain TEXT, protocol TEXT, position_type VARCHAR(20) NOT NULL DEFAULT 'HOLDING',
        icon_url TEXT
    );

    CREATE TABLE crypto_currency_initial_investments (
        id CHAR(36) PRIMARY KEY, crypto_currency_position CHAR(36),
        currency CHAR(3), initial_investment TEXT, average_buy_price TEXT
    );

    CREATE TABLE crypto_assets (
        id CHAR(36) PRIMARY KEY, name TEXT, symbol TEXT, icon_urls TEXT, external_ids TEXT
    );
"""


@pytest_asyncio.fixture
async def repo():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(_SCHEMA)
    db_client = DBClient(conn)
    yield PositionSQLRepository(client=db_client)
    conn.close()


@pytest.mark.asyncio
async def test_defi_position_round_trips_labels_and_negative_value(repo):
    entity = Entity(
        id=uuid4(),
        name="Aave",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.NATIVE,
        icon_url=None,
    )
    gp_id = uuid4()
    position = GlobalPosition(
        id=gp_id,
        entity=entity,
        date=datetime.now(tzlocal()),
        source=DataSource.REAL,
        products={
            ProductType.CRYPTO: CryptoCurrencies(
                entries=[
                    CryptoCurrencyWallet(
                        assets=[
                            CryptoCurrencyPosition(
                                id=uuid4(),
                                symbol="debtUSDC",
                                amount=Dezimal("-50"),
                                type=CryptoCurrencyType.TOKEN,
                                chain="ethereum",
                                protocol="Aave V3",
                                position_type=CryptoPositionType.BORROWED,
                                market_value=Dezimal("-50"),
                                currency="EUR",
                                icon_url="https://fake-zerion-cdn.example/protocols/aave.png",
                            )
                        ]
                    )
                ]
            )
        },
    )

    await repo.save(position)

    loaded = await repo._get_all_cryptocurrency([position])
    assets = loaded[gp_id].entries[0].assets

    assert len(assets) == 1
    loaded_pos = assets[0]
    assert loaded_pos.chain == "ethereum"
    assert loaded_pos.protocol == "Aave V3"
    assert loaded_pos.position_type == CryptoPositionType.BORROWED
    assert loaded_pos.market_value == Dezimal("-50")
    assert loaded_pos.amount == Dezimal("-50")
    assert loaded_pos.icon_url == "https://fake-zerion-cdn.example/protocols/aave.png"
