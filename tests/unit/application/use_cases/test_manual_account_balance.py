from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from application.ports.exchange_rate_provider import ExchangeRateProvider
from application.ports.position_port import PositionPort
from application.use_cases.manual_account_balance import ManualAccountBalanceUpdater
from application.use_cases.manual_position_snapshot import (
    ManualPositionSnapshotWriter,
)
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import ManualAccountNotFound
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    GlobalPosition,
    ProductType,
)


def _make_entity(entity_id=None, name="ManualBank"):
    return Entity(
        id=entity_id or uuid4(),
        name=name,
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _make_account(
    account_id=None,
    total=Dezimal(1000),
    currency="EUR",
    source=DataSource.MANUAL,
):
    return Account(
        id=account_id or uuid4(),
        total=total,
        currency=currency,
        type=AccountType.CHECKING,
        name="Main",
        iban="ES0000000000000000001234",
        source=source,
    )


def _make_position(entity, accounts):
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        products={ProductType.ACCOUNT: Accounts(entries=accounts)},
    )


def _build_updater():
    position_port = AsyncMock(spec=PositionPort)
    snapshot_writer = AsyncMock(spec=ManualPositionSnapshotWriter)
    exchange_rate_provider = AsyncMock(spec=ExchangeRateProvider)
    updater = ManualAccountBalanceUpdater(
        position_port=position_port,
        snapshot_writer=snapshot_writer,
        exchange_rate_provider=exchange_rate_provider,
    )
    return updater, position_port, snapshot_writer, exchange_rate_provider


@pytest.mark.asyncio
async def test_prepare_not_found_raises():
    updater, position_port, _, _ = _build_updater()
    position_port.get_last_grouped_by_entity.return_value = {}

    with pytest.raises(ManualAccountNotFound):
        await updater.prepare(uuid4(), Dezimal(50), "EUR")


@pytest.mark.asyncio
async def test_prepare_rejects_real_account():
    updater, position_port, _, _ = _build_updater()
    entity = _make_entity()
    account = _make_account(source=DataSource.REAL)
    position_port.get_last_grouped_by_entity.return_value = {
        entity: _make_position(entity, [account])
    }

    with pytest.raises(ManualAccountNotFound):
        await updater.prepare(account.id, Dezimal(50), "EUR")


@pytest.mark.asyncio
async def test_prepare_filters_by_entity_id():
    updater, position_port, _, _ = _build_updater()
    target_entity = _make_entity(name="Target")
    other_entity = _make_entity(name="Other")
    other_account = _make_account()
    position_port.get_last_grouped_by_entity.return_value = {
        other_entity: _make_position(other_entity, [other_account])
    }

    with pytest.raises(ManualAccountNotFound):
        await updater.prepare(
            other_account.id, Dezimal(50), "EUR", entity_id=target_entity.id
        )

    query = position_port.get_last_grouped_by_entity.await_args[0][0]
    assert query.entities == [target_entity.id]
    assert query.real is False
    assert query.products is None


@pytest.mark.asyncio
async def test_prepare_same_currency_skips_fx_matrix():
    updater, position_port, _, fx_provider = _build_updater()
    entity = _make_entity()
    account = _make_account(total=Dezimal(1000), currency="EUR")
    position = _make_position(entity, [account])
    old_position_id = position.id
    position_port.get_last_grouped_by_entity.return_value = {entity: position}

    update = await updater.prepare(account.id, Dezimal("-125.50"), "eur")

    assert account.total == Dezimal("874.50")
    assert update.entity is entity
    assert update.position is position
    assert position.id != old_position_id
    assert position.source == DataSource.MANUAL
    fx_provider.get_matrix.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_converts_cross_currency():
    updater, position_port, _, fx_provider = _build_updater()
    entity = _make_entity()
    account = _make_account(total=Dezimal(1000), currency="EUR")
    position_port.get_last_grouped_by_entity.return_value = {
        entity: _make_position(entity, [account])
    }
    fx_provider.get_matrix.return_value = {"EUR": {"USD": Dezimal("1.25")}}

    await updater.prepare(account.id, Dezimal("250"), "USD")

    assert account.total == Dezimal("1200")
    fx_provider.get_matrix.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "matrix",
    [{}, {"EUR": {"USD": Dezimal(0)}}],
)
async def test_prepare_missing_or_zero_rate_raises(matrix):
    updater, position_port, _, fx_provider = _build_updater()
    entity = _make_entity()
    account = _make_account(total=Dezimal(1000), currency="EUR")
    position_port.get_last_grouped_by_entity.return_value = {
        entity: _make_position(entity, [account])
    }
    fx_provider.get_matrix.return_value = matrix

    with pytest.raises(ValueError, match="exchange rate"):
        await updater.prepare(account.id, Dezimal("100"), "USD")


@pytest.mark.asyncio
async def test_write_delegates_to_snapshot_writer():
    updater, position_port, snapshot_writer, _ = _build_updater()
    entity = _make_entity()
    account = _make_account(total=Dezimal(500))
    position = _make_position(entity, [account])
    position_port.get_last_grouped_by_entity.return_value = {entity: position}

    update = await updater.prepare(account.id, Dezimal(100), "EUR")
    await updater.write(update)

    snapshot_writer.write.assert_awaited_once_with(entity, position)
