from datetime import datetime
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.use_cases.delete_crypto_wallet import DeleteCryptoWalletConnectionImpl
from domain.crypto import AddressSource, CryptoCurrencyType, CryptoWallet
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import (
    CryptoCurrencies,
    CryptoCurrencyPosition,
    CryptoCurrencyWallet,
    GlobalPosition,
    PositionQueryRequest,
    ProductType,
)
from infrastructure.repository.crypto.crypto_wallet_repository import (
    CryptoWalletRepository,
)
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.repository.entity.entity_repository import EntitySQLRepository
from infrastructure.repository.position.position_repository import (
    PositionSQLRepository,
)


async def _signup(client):
    response = await client.post(
        "/api/v1/signup",
        json={"username": "testuser", "password": "securePass123"},
    )
    assert response.status_code == 204


def _make_entity():
    return Entity(
        id=uuid4(),
        name="Ethereum",
        natural_id=None,
        type=EntityType.CRYPTO_WALLET,
        origin=EntityOrigin.NATIVE,
        icon_url=None,
    )


def _make_wallet(wallet_id, entity_id, name):
    return CryptoWallet(
        id=wallet_id,
        entity_id=entity_id,
        addresses=[f"0x{name}"],
        name=name,
        address_source=AddressSource.MANUAL,
        hd_wallet=None,
    )


def _make_position(
    entity, position_id, position_date, deleted_wallet_id, surviving_wallet_id
):
    deleted_asset = CryptoCurrencyPosition(
        id=uuid4(),
        symbol="ETH",
        name="Ethereum",
        amount=Dezimal("1"),
        type=CryptoCurrencyType.NATIVE,
    )
    surviving_asset = CryptoCurrencyPosition(
        id=uuid4(),
        symbol="BTC",
        name="Bitcoin",
        amount=Dezimal("2"),
        type=CryptoCurrencyType.NATIVE,
        initial_investment=Dezimal("100"),
        investment_currency="EUR",
    )
    return GlobalPosition(
        id=position_id,
        entity=entity,
        date=position_date,
        source=DataSource.REAL,
        products={
            ProductType.CRYPTO: CryptoCurrencies(
                entries=[
                    CryptoCurrencyWallet(id=deleted_wallet_id, assets=[deleted_asset]),
                    CryptoCurrencyWallet(
                        id=surviving_wallet_id, assets=[surviving_asset]
                    ),
                ]
            )
        },
    )


@pytest.mark.asyncio
async def test_delete_wallet_creates_clean_current_snapshot_and_keeps_history(
    client, db_client
):
    await _signup(client)

    entity = _make_entity()
    deleted_wallet_id = uuid4()
    surviving_wallet_id = uuid4()
    old_position_id = uuid4()
    current_position_id = uuid4()
    entity_repo = EntitySQLRepository(client=db_client)
    wallet_repo = CryptoWalletRepository(client=db_client)
    position_repo = PositionSQLRepository(client=db_client)

    await entity_repo.insert(entity)
    await wallet_repo.insert(_make_wallet(deleted_wallet_id, entity.id, "deleted"))
    await wallet_repo.insert(_make_wallet(surviving_wallet_id, entity.id, "surviving"))
    await position_repo.save(
        _make_position(
            entity,
            old_position_id,
            datetime(2025, 1, 1, tzinfo=tzlocal()),
            deleted_wallet_id,
            surviving_wallet_id,
        )
    )
    await position_repo.save(
        _make_position(
            entity,
            current_position_id,
            datetime(2025, 1, 2, tzinfo=tzlocal()),
            deleted_wallet_id,
            surviving_wallet_id,
        )
    )

    use_case = DeleteCryptoWalletConnectionImpl(
        wallet_repo,
        position_repo,
        TransactionHandler(client=db_client),
    )
    await use_case.execute(deleted_wallet_id)

    positions_by_entity = await position_repo.get_last_by_entity_broken_down(
        PositionQueryRequest(entities=[entity.id], real=True)
    )
    current_position = next(
        position
        for result_entity, positions in positions_by_entity.items()
        if result_entity.id == entity.id
        for position in positions
    )
    current_crypto = current_position.products[ProductType.CRYPTO]
    assert [wallet.id for wallet in current_crypto.entries] == [surviving_wallet_id]
    assert current_position.id not in {old_position_id, current_position_id}
    assert current_crypto.entries[0].assets[0].initial_investment == Dezimal("100")

    assert await wallet_repo.get_by_id(deleted_wallet_id) is None
    assert await wallet_repo.get_by_id(surviving_wallet_id) is not None

    async with db_client.read() as cursor:
        await cursor.execute(
            "SELECT id FROM global_positions WHERE id = ?",
            (str(old_position_id),),
        )
        assert await cursor.fetchone() is not None

        await cursor.execute(
            "SELECT symbol, wallet_id FROM crypto_currency_positions "
            "WHERE global_position_id = ?",
            (str(old_position_id),),
        )
        history_rows = {
            row["symbol"]: row["wallet_id"] for row in await cursor.fetchall()
        }

    assert history_rows["ETH"] is None
    assert history_rows["BTC"] == str(surviving_wallet_id)
