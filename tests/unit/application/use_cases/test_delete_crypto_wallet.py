from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.ports.crypto_wallet_port import CryptoWalletPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
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
    ProductType,
)


def _make_entity():
    return Entity(
        id=uuid4(),
        name="Crypto wallet",
        natural_id=None,
        type=EntityType.CRYPTO_WALLET,
        origin=EntityOrigin.NATIVE,
        icon_url=None,
    )


def _make_wallet(wallet_id, entity_id):
    return CryptoWallet(
        id=wallet_id,
        entity_id=entity_id,
        addresses=["0xabc"],
        name="Wallet",
        address_source=AddressSource.MANUAL,
        hd_wallet=None,
    )


def _make_position(entity, deleted_wallet_id, surviving_wallet_id):
    deleted_asset = CryptoCurrencyPosition(
        id=uuid4(),
        symbol="ETH",
        amount=Dezimal("1"),
        type=CryptoCurrencyType.NATIVE,
    )
    surviving_asset = CryptoCurrencyPosition(
        id=uuid4(),
        symbol="BTC",
        amount=Dezimal("2"),
        type=CryptoCurrencyType.NATIVE,
        initial_investment=Dezimal("100"),
        investment_currency="EUR",
    )
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        date=datetime.now(tzlocal()),
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
async def test_delete_wallet_saves_filtered_snapshot_before_delete():
    entity = _make_entity()
    deleted_wallet_id = uuid4()
    surviving_wallet_id = uuid4()
    second_surviving_wallet_id = uuid4()
    position = _make_position(entity, deleted_wallet_id, surviving_wallet_id)
    second_surviving_asset = CryptoCurrencyPosition(
        id=uuid4(),
        symbol="USDC",
        amount=Dezimal("3"),
        type=CryptoCurrencyType.TOKEN,
    )
    position.products[ProductType.CRYPTO].entries.append(
        CryptoCurrencyWallet(
            id=second_surviving_wallet_id,
            assets=[second_surviving_asset],
        )
    )
    wallet_port = AsyncMock(spec=CryptoWalletPort)
    wallet_port.get_by_id.return_value = _make_wallet(deleted_wallet_id, entity.id)
    position_port = AsyncMock(spec=PositionPort)
    position_port.get_last_by_entity_broken_down.return_value = {entity: [position]}
    transaction_handler = MagicMock(spec=TransactionHandlerPort)
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    transaction_handler.start = MagicMock(return_value=transaction)
    calls = []
    position_port.save.side_effect = lambda _: calls.append("save")
    wallet_port.delete.side_effect = lambda _: calls.append("delete")

    use_case = DeleteCryptoWalletConnectionImpl(
        wallet_port, position_port, transaction_handler
    )

    await use_case.execute(deleted_wallet_id)

    saved_position = position_port.save.await_args.args[0]
    saved_crypto = saved_position.products[ProductType.CRYPTO]
    assert saved_position.id != position.id
    assert saved_position.source == DataSource.REAL
    assert [wallet.id for wallet in saved_crypto.entries] == [
        surviving_wallet_id,
        second_surviving_wallet_id,
    ]
    assert (
        saved_crypto.entries[0].assets[0].id
        != position.products[ProductType.CRYPTO].entries[1].assets[0].id
    )
    assert saved_crypto.entries[1].assets[0].id != second_surviving_asset.id
    assert saved_crypto.entries[0].assets[0].initial_investment == Dezimal("100")
    assert calls == ["save", "delete"]
    transaction.__aenter__.assert_awaited_once()
    wallet_port.delete.assert_awaited_once_with(deleted_wallet_id)
