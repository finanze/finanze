import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest
from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.historic import FactoringEntry, HistoricState
from domain.transactions import FactoringTx, Transactions, TxType

ENTITY_ID = "e0000000-0000-0000-0000-000000000001"
ENTRY_ID = "a0000000-0000-0000-0000-000000000010"


def _make_entity():
    return Entity(
        id=uuid.UUID(ENTITY_ID),
        name="Manual",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _make_tx(entity, tx_date, amount, tx_type):
    return FactoringTx(
        id=uuid.uuid4(),
        ref=f"manual-{uuid.uuid4().hex}",
        name="Loan A",
        amount=amount,
        currency="EUR",
        type=tx_type,
        date=tx_date,
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.FACTORING,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        net_amount=amount,
    )


def _make_entry(entity, related_txs, maturity, source=DataSource.MANUAL, state=None):
    return FactoringEntry(
        id=uuid.UUID(ENTRY_ID),
        name="Loan A",
        invested=Dezimal("1000"),
        repaid=Dezimal("1000"),
        returned=Dezimal("1100"),
        currency="EUR",
        last_invest_date=datetime(2024, 1, 1, tzinfo=tzlocal()),
        last_tx_date=maturity,
        effective_maturity=maturity,
        net_return=Dezimal("100"),
        fees=Dezimal(0),
        retentions=Dezimal(0),
        interests=Dezimal("100"),
        state=state or HistoricState.COMPLETED.value,
        entity=entity,
        product_type=ProductType.FACTORING,
        related_txs=related_txs,
        entity_account_id=None,
        source=source,
        manual_key="key-1",
        interest_rate=Dezimal("0.1"),
        gross_interest_rate=Dezimal("0.1"),
        maturity=date(2024, 12, 31),
        type="SIMPLE",
    )


def _configure_ports(historic_port, transaction_port, entry):
    historic_port.get_by_id = AsyncMock(return_value=entry)
    historic_port.upsert = AsyncMock()
    historic_port.delete_by_id = AsyncMock()
    transaction_port.get_by_entity_and_source = AsyncMock(
        return_value=Transactions(investment=[], account=[])
    )
    transaction_port.save = AsyncMock()
    transaction_port.delete_by_id = AsyncMock()


class TestUnsettleManualInvestment:
    @pytest.mark.asyncio
    async def test_unsettle_not_found(self, client, historic_port, transaction_port):
        entity = _make_entity()
        entry = _make_entry(entity, [], datetime.now(tzlocal()))
        _configure_ports(historic_port, transaction_port, entry)
        historic_port.get_by_id = AsyncMock(return_value=None)

        response = await client.post(f"/api/v1/historic/{ENTRY_ID}/unsettle")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unsettle_not_final_returns_409(
        self, client, historic_port, transaction_port
    ):
        entity = _make_entity()
        entry = _make_entry(entity, [], datetime.now(tzlocal()), state="OUTSTANDING")
        _configure_ports(historic_port, transaction_port, entry)

        response = await client.post(f"/api/v1/historic/{ENTRY_ID}/unsettle")

        assert response.status_code == 409


class TestDeleteManualHistoricEntry:
    @pytest.mark.asyncio
    async def test_delete_none_returns_204(
        self, client, historic_port, transaction_port
    ):
        entity = _make_entity()
        maturity = datetime(2024, 12, 31, tzinfo=tzlocal())
        txs = [_make_tx(entity, maturity, Dezimal("1000"), TxType.REPAYMENT)]
        entry = _make_entry(entity, txs, maturity)
        _configure_ports(historic_port, transaction_port, entry)

        response = await client.delete(f"/api/v1/historic/{ENTRY_ID}")

        assert response.status_code == 204
        transaction_port.delete_by_id.assert_not_awaited()
        historic_port.delete_by_id.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_all_removes_txs(
        self, client, historic_port, transaction_port
    ):
        entity = _make_entity()
        maturity = datetime(2024, 12, 31, tzinfo=tzlocal())
        txs = [
            _make_tx(entity, maturity, Dezimal("1000"), TxType.REPAYMENT),
            _make_tx(entity, maturity, Dezimal("100"), TxType.INTEREST),
        ]
        entry = _make_entry(entity, txs, maturity)
        _configure_ports(historic_port, transaction_port, entry)

        response = await client.delete(f"/api/v1/historic/{ENTRY_ID}?tx_deletion=ALL")

        assert response.status_code == 204
        assert transaction_port.delete_by_id.await_count == 2

    @pytest.mark.asyncio
    async def test_delete_invalid_mode_returns_400(
        self, client, historic_port, transaction_port
    ):
        entity = _make_entity()
        entry = _make_entry(entity, [], datetime.now(tzlocal()))
        _configure_ports(historic_port, transaction_port, entry)

        response = await client.delete(f"/api/v1/historic/{ENTRY_ID}?tx_deletion=BOGUS")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client, historic_port, transaction_port):
        entity = _make_entity()
        entry = _make_entry(entity, [], datetime.now(tzlocal()))
        _configure_ports(historic_port, transaction_port, entry)
        historic_port.get_by_id = AsyncMock(return_value=None)

        response = await client.delete(f"/api/v1/historic/{ENTRY_ID}")

        assert response.status_code == 404
