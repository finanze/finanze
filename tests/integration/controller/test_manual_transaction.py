import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.transactions import (
    AccountTx,
    CryptoCurrencyTx,
    StockTx,
    Transactions,
    TxType,
)

ADD_TX_URL = "/api/v1/data/manual/transactions"
GET_TX_URL = "/api/v1/transactions"
ENTITY_ID = "e0000000-0000-0000-0000-000000000001"
REAL_ENTITY_ID = "e0000000-0000-0000-0000-000000000099"


def _make_entity(entity_id=ENTITY_ID, name="Test Entity", origin=EntityOrigin.MANUAL):
    return Entity(
        id=uuid.UUID(entity_id),
        name=name,
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=origin,
        icon_url=None,
    )


def _account_tx_payload(**overrides):
    base = {
        "product_type": "ACCOUNT",
        "entity_id": ENTITY_ID,
        "date": "2025-01-15T10:00:00",
        "ref": "TX-001",
        "name": "Salary",
        "amount": "2500.00",
        "currency": "EUR",
        "type": "TRANSFER_IN",
    }
    base.update(overrides)
    return base


def _stock_tx_payload(**overrides):
    base = {
        "product_type": "STOCK_ETF",
        "entity_id": ENTITY_ID,
        "date": "2025-02-01T09:30:00",
        "ref": "TX-002",
        "name": "Buy ACME",
        "amount": "1000.00",
        "currency": "EUR",
        "type": "BUY",
        "shares": "10",
        "price": "100.00",
        "fees": "5.00",
    }
    base.update(overrides)
    return base


def _crypto_tx_payload(**overrides):
    base = {
        "product_type": "CRYPTO",
        "entity_id": ENTITY_ID,
        "date": "2025-03-10T14:00:00",
        "ref": "TX-CRYPTO-001",
        "name": "Buy BTC",
        "amount": "5000.00",
        "currency": "EUR",
        "type": "BUY",
        "symbol": "BTC",
        "currency_amount": "0.05",
        "price": "100000.00",
    }
    base.update(overrides)
    return base


def _make_real_account_tx(entity):
    return AccountTx(
        id=uuid.uuid4(),
        ref="REAL-TX-001",
        name="Real Salary",
        amount=Dezimal("5000"),
        currency="EUR",
        type=TxType.TRANSFER_IN,
        date=datetime(2025, 1, 10, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.REAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal("0"),
        retentions=Dezimal("0"),
    )


class TestAddManualTransactionValidation:
    @pytest.mark.asyncio
    async def test_missing_product_type(self, client):
        payload = {"entity_id": ENTITY_ID, "date": "2025-01-01T00:00:00"}
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"

    @pytest.mark.asyncio
    async def test_missing_entity_id(self, client):
        payload = {
            "product_type": "ACCOUNT",
            "date": "2025-01-01T00:00:00",
            "ref": "TX",
            "name": "Test",
            "amount": "100",
            "currency": "EUR",
            "type": "TRANSFER_IN",
        }
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, client):
        payload = {
            "product_type": "ACCOUNT",
            "entity_id": ENTITY_ID,
            "date": "2025-01-01T00:00:00",
        }
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_product_type(self, client):
        payload = _account_tx_payload(product_type="INVALID")
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_stock_missing_required_fields(self, client):
        payload = {
            "product_type": "STOCK_ETF",
            "entity_id": ENTITY_ID,
            "date": "2025-01-01T00:00:00",
            "ref": "TX",
            "name": "Buy",
            "amount": "100",
            "currency": "EUR",
            "type": "BUY",
        }
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 400
        body = await response.get_json()
        assert "Missing fields" in body["message"]

    @pytest.mark.asyncio
    async def test_unsupported_product_type(self, client):
        payload = _account_tx_payload(product_type="UNKNOWN_TYPE")
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 400


class TestAddManualTransactionEntityNotFound:
    @pytest.mark.asyncio
    async def test_entity_not_found(self, client, entity_port):
        entity_port.get_by_id = AsyncMock(return_value=None)
        response = await client.post(ADD_TX_URL, json=_account_tx_payload())
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "ENTITY_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_entity_not_found_stock(self, client, entity_port):
        entity_port.get_by_id = AsyncMock(return_value=None)
        response = await client.post(ADD_TX_URL, json=_stock_tx_payload())
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "ENTITY_NOT_FOUND"


class TestAddAccountTransactionAndRead:
    @pytest.mark.asyncio
    async def test_add_account_tx_then_read_it(
        self, client, entity_port, transaction_port, virtual_import_registry
    ):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        response = await client.post(ADD_TX_URL, json=_account_tx_payload())
        assert response.status_code == 204

        transaction_port.save.assert_awaited_once()
        saved_txs = transaction_port.save.await_args[0][0]
        assert isinstance(saved_txs, Transactions)
        assert len(saved_txs.account) == 1
        saved_tx = saved_txs.account[0]
        assert saved_tx.name == "Salary"
        assert saved_tx.amount == Dezimal("2500.00")
        assert saved_tx.source == DataSource.MANUAL

        # Read back via GET /transactions
        transaction_port.get_by_filters = AsyncMock(return_value=[saved_tx])
        get_resp = await client.get(GET_TX_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        txs = body["transactions"]
        assert len(txs) == 1
        assert txs[0]["name"] == "Salary"
        assert txs[0]["amount"] == 2500.0
        assert txs[0]["source"] == "MANUAL"
        assert txs[0]["currency"] == "EUR"

    @pytest.mark.asyncio
    async def test_add_account_tx_with_fees(
        self, client, entity_port, transaction_port, virtual_import_registry
    ):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        payload = _account_tx_payload(fees="10.50", retentions="2.00")
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 204

        saved_txs = transaction_port.save.await_args[0][0]
        tx = saved_txs.account[0]
        assert tx.fees == Dezimal("10.50")
        assert tx.retentions == Dezimal("2.00")

    @pytest.mark.asyncio
    async def test_add_account_tx_with_interest(
        self, client, entity_port, transaction_port, virtual_import_registry
    ):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        payload = _account_tx_payload(
            type="INTEREST", interest_rate="3.5", avg_balance="50000"
        )
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 204

        saved_txs = transaction_port.save.await_args[0][0]
        tx = saved_txs.account[0]
        assert tx.interest_rate == Dezimal("3.5")
        assert tx.avg_balance == Dezimal("50000")


class TestAddStockTransactionAndRead:
    @pytest.mark.asyncio
    async def test_add_stock_tx_then_read_it(
        self, client, entity_port, transaction_port, virtual_import_registry
    ):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        response = await client.post(ADD_TX_URL, json=_stock_tx_payload())
        assert response.status_code == 204

        transaction_port.save.assert_awaited_once()
        saved_txs = transaction_port.save.await_args[0][0]
        saved_tx = saved_txs.investment[0]
        assert isinstance(saved_tx, StockTx)
        assert saved_tx.shares == Dezimal("10")
        assert saved_tx.price == Dezimal("100.00")
        assert saved_tx.fees == Dezimal("5.00")

        # Read back
        transaction_port.get_by_filters = AsyncMock(return_value=[saved_tx])
        get_resp = await client.get(GET_TX_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        txs = body["transactions"]
        assert len(txs) == 1
        assert txs[0]["name"] == "Buy ACME"
        assert txs[0]["shares"] == 10.0
        assert txs[0]["price"] == 100.0
        assert txs[0]["source"] == "MANUAL"

    @pytest.mark.asyncio
    async def test_add_stock_tx_with_optional_fields(
        self, client, entity_port, transaction_port, virtual_import_registry
    ):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        payload = _stock_tx_payload(
            isin="US0000000001",
            ticker="ACME",
            market="NYSE",
            retentions="1.50",
        )
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 204

        saved_txs = transaction_port.save.await_args[0][0]
        tx = saved_txs.investment[0]
        assert tx.isin == "US0000000001"
        assert tx.ticker == "ACME"
        assert tx.market == "NYSE"


class TestCoexistenceWithRealTransactions:
    @pytest.mark.asyncio
    async def test_manual_and_real_txs_both_returned(
        self, client, entity_port, transaction_port, virtual_import_registry
    ):
        manual_entity = _make_entity()
        real_entity = _make_entity(REAL_ENTITY_ID, "Real Bank", EntityOrigin.NATIVE)

        entity_port.get_by_id = AsyncMock(return_value=manual_entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        response = await client.post(ADD_TX_URL, json=_account_tx_payload())
        assert response.status_code == 204

        saved_manual_tx = transaction_port.save.await_args[0][0].account[0]
        real_tx = _make_real_account_tx(real_entity)

        # GET returns both manual and real
        transaction_port.get_by_filters = AsyncMock(
            return_value=[saved_manual_tx, real_tx]
        )
        get_resp = await client.get(GET_TX_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        txs = body["transactions"]
        assert len(txs) == 2
        sources = {t["source"] for t in txs}
        assert sources == {"MANUAL", "REAL"}

        manual = next(t for t in txs if t["source"] == "MANUAL")
        assert manual["name"] == "Salary"

        real = next(t for t in txs if t["source"] == "REAL")
        assert real["name"] == "Real Salary"
        assert real["amount"] == 5000.0


class TestAddFundTransaction:
    @pytest.mark.asyncio
    async def test_add_fund_tx_success(
        self, client, entity_port, transaction_port, virtual_import_registry
    ):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        payload = {
            "product_type": "FUND",
            "entity_id": ENTITY_ID,
            "date": "2025-03-01T12:00:00",
            "ref": "TX-FUND",
            "name": "Buy Fund",
            "amount": "5000.00",
            "currency": "EUR",
            "type": "BUY",
            "isin": "LU0000000001",
            "shares": "50",
            "price": "100",
            "fees": "10",
        }
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 204

        saved_txs = transaction_port.save.await_args[0][0]
        assert len(saved_txs.investment) == 1

    @pytest.mark.asyncio
    async def test_fund_missing_isin(self, client):
        payload = {
            "product_type": "FUND",
            "entity_id": ENTITY_ID,
            "date": "2025-03-01T12:00:00",
            "ref": "TX-FUND",
            "name": "Buy Fund",
            "amount": "5000",
            "currency": "EUR",
            "type": "BUY",
            "shares": "50",
            "price": "100",
            "fees": "10",
        }
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 400


class TestAddFactoringTransaction:
    @pytest.mark.asyncio
    async def test_add_factoring_tx_success(
        self, client, entity_port, transaction_port, virtual_import_registry
    ):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        payload = {
            "product_type": "FACTORING",
            "entity_id": ENTITY_ID,
            "date": "2025-04-01T00:00:00",
            "ref": "TX-FACT",
            "name": "Factoring Payment",
            "amount": "3000",
            "currency": "EUR",
            "type": "INVESTMENT",
            "fees": "15",
            "retentions": "5",
        }
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 204
        transaction_port.save.assert_awaited_once()


class TestUpdateManualTransactionAndRead:
    @pytest.mark.asyncio
    async def test_update_invalid_tx_id(self, client):
        response = await client.put(
            f"{ADD_TX_URL}/not-a-uuid",
            json=_account_tx_payload(),
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"

    @pytest.mark.asyncio
    async def test_update_tx_not_found(self, client, transaction_port):
        tx_id = str(uuid.uuid4())
        transaction_port.get_by_id = AsyncMock(return_value=None)

        response = await client.put(
            f"{ADD_TX_URL}/{tx_id}",
            json=_account_tx_payload(),
        )
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_non_manual_tx_returns_not_found(
        self, client, transaction_port
    ):
        tx_id = uuid.uuid4()
        existing_tx = MagicMock()
        existing_tx.source = DataSource.REAL
        existing_tx.entity = _make_entity()
        existing_tx.product_type = ProductType.ACCOUNT
        transaction_port.get_by_id = AsyncMock(return_value=existing_tx)

        response = await client.put(
            f"{ADD_TX_URL}/{tx_id}",
            json=_account_tx_payload(),
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_account_tx_then_read_it(
        self,
        client,
        entity_port,
        transaction_port,
        virtual_import_registry,
    ):
        tx_id = uuid.uuid4()
        existing_tx = MagicMock()
        existing_tx.id = tx_id
        existing_tx.source = DataSource.MANUAL
        existing_tx.entity = _make_entity()
        existing_tx.product_type = ProductType.ACCOUNT
        transaction_port.get_by_id = AsyncMock(return_value=existing_tx)
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        payload = _account_tx_payload(name="Updated Salary", amount="3000.00")
        response = await client.put(f"{ADD_TX_URL}/{tx_id}", json=payload)
        assert response.status_code == 204

        transaction_port.delete_by_id.assert_awaited_once_with(tx_id)
        transaction_port.save.assert_awaited_once()
        saved_tx = transaction_port.save.await_args[0][0].account[0]

        # Read back updated tx
        transaction_port.get_by_filters = AsyncMock(return_value=[saved_tx])
        get_resp = await client.get(GET_TX_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        txs = body["transactions"]
        assert len(txs) == 1
        assert txs[0]["name"] == "Updated Salary"
        assert txs[0]["amount"] == 3000.0
        assert txs[0]["source"] == "MANUAL"

    @pytest.mark.asyncio
    async def test_update_stock_tx_success(
        self,
        client,
        entity_port,
        transaction_port,
        virtual_import_registry,
    ):
        tx_id = uuid.uuid4()
        existing_tx = MagicMock()
        existing_tx.id = tx_id
        existing_tx.source = DataSource.MANUAL
        existing_tx.entity = _make_entity()
        existing_tx.product_type = ProductType.STOCK_ETF
        transaction_port.get_by_id = AsyncMock(return_value=existing_tx)
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        payload = _stock_tx_payload(
            name="Updated Buy", shares="20", price="110.00", fees="8.00"
        )
        response = await client.put(f"{ADD_TX_URL}/{tx_id}", json=payload)
        assert response.status_code == 204

        saved_txs = transaction_port.save.await_args[0][0]
        tx = saved_txs.investment[0]
        assert tx.shares == Dezimal("20")
        assert tx.price == Dezimal("110.00")


class TestDeleteManualTransactionAndRead:
    @pytest.mark.asyncio
    async def test_delete_invalid_tx_id(self, client):
        response = await client.delete(f"{ADD_TX_URL}/not-a-uuid")
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"

    @pytest.mark.asyncio
    async def test_delete_tx_not_found(self, client, transaction_port):
        tx_id = str(uuid.uuid4())
        transaction_port.get_by_id = AsyncMock(return_value=None)

        response = await client.delete(f"{ADD_TX_URL}/{tx_id}")
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "TX_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_non_manual_tx(self, client, transaction_port):
        tx_id = uuid.uuid4()
        existing_tx = MagicMock()
        existing_tx.source = DataSource.REAL
        existing_tx.entity = _make_entity()
        transaction_port.get_by_id = AsyncMock(return_value=existing_tx)

        response = await client.delete(f"{ADD_TX_URL}/{tx_id}")
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "TX_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_manual_tx_real_tx_still_visible(
        self,
        client,
        entity_port,
        transaction_port,
        virtual_import_registry,
    ):
        real_entity = _make_entity(REAL_ENTITY_ID, "Real Bank", EntityOrigin.NATIVE)
        tx_id = uuid.uuid4()
        existing_tx = MagicMock()
        existing_tx.id = tx_id
        existing_tx.source = DataSource.MANUAL
        existing_tx.entity = _make_entity()

        transaction_port.get_by_id = AsyncMock(return_value=existing_tx)
        transaction_port.get_by_entity_and_source = AsyncMock(
            return_value=Transactions(account=[], investment=[])
        )
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        response = await client.delete(f"{ADD_TX_URL}/{tx_id}")
        assert response.status_code == 204
        transaction_port.delete_by_id.assert_awaited_once_with(tx_id)

        # After deleting the manual tx, GET returns only real txs
        real_tx = _make_real_account_tx(real_entity)
        transaction_port.get_by_filters = AsyncMock(return_value=[real_tx])
        get_resp = await client.get(GET_TX_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        txs = body["transactions"]
        assert len(txs) == 1
        assert txs[0]["source"] == "REAL"
        assert txs[0]["name"] == "Real Salary"

    @pytest.mark.asyncio
    async def test_delete_with_remaining_manual_txs(
        self,
        client,
        transaction_port,
        virtual_import_registry,
    ):
        tx_id = uuid.uuid4()
        existing_tx = MagicMock()
        existing_tx.id = tx_id
        existing_tx.source = DataSource.MANUAL
        existing_tx.entity = _make_entity()

        remaining_tx = AccountTx(
            id=uuid.uuid4(),
            ref="TX-REM",
            name="Remaining",
            amount=Dezimal("100"),
            currency="EUR",
            type=TxType.TRANSFER_IN,
            date=datetime(2025, 1, 1, tzinfo=tzlocal()),
            entity=_make_entity(),
            source=DataSource.MANUAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal("0"),
            retentions=Dezimal("0"),
        )
        transaction_port.get_by_id = AsyncMock(return_value=existing_tx)
        transaction_port.get_by_entity_and_source = AsyncMock(
            return_value=Transactions(account=[remaining_tx], investment=[])
        )
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        response = await client.delete(f"{ADD_TX_URL}/{tx_id}")
        assert response.status_code == 204
        transaction_port.delete_by_id.assert_awaited_once_with(tx_id)
        virtual_import_registry.insert.assert_awaited_once()

        # Remaining tx is still visible
        transaction_port.get_by_filters = AsyncMock(return_value=[remaining_tx])
        get_resp = await client.get(GET_TX_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        txs = body["transactions"]
        assert len(txs) == 1
        assert txs[0]["name"] == "Remaining"
        assert txs[0]["source"] == "MANUAL"


class TestAddCryptoTransaction:
    @pytest.mark.asyncio
    async def test_add_crypto_tx_then_read_it(
        self, client, entity_port, transaction_port, virtual_import_registry
    ):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        response = await client.post(ADD_TX_URL, json=_crypto_tx_payload())
        assert response.status_code == 204

        transaction_port.save.assert_awaited_once()
        saved_txs = transaction_port.save.await_args[0][0]
        assert len(saved_txs.investment) == 1
        saved_tx = saved_txs.investment[0]
        assert isinstance(saved_tx, CryptoCurrencyTx)
        assert saved_tx.symbol == "BTC"
        assert saved_tx.currency_amount == Dezimal("0.05")
        assert saved_tx.price == Dezimal("100000.00")
        assert saved_tx.fees == Dezimal("0")
        assert saved_tx.source == DataSource.MANUAL

        transaction_port.get_by_filters = AsyncMock(return_value=[saved_tx])
        get_resp = await client.get(GET_TX_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        txs = body["transactions"]
        assert len(txs) == 1
        assert txs[0]["name"] == "Buy BTC"
        assert txs[0]["symbol"] == "BTC"
        assert txs[0]["source"] == "MANUAL"

    @pytest.mark.asyncio
    async def test_add_crypto_tx_with_optional_fields(
        self, client, entity_port, transaction_port, virtual_import_registry
    ):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        payload = _crypto_tx_payload(
            fees="2.50",
            retentions="1.00",
            order_date="2025-03-10T12:00:00",
        )
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 204

        saved_txs = transaction_port.save.await_args[0][0]
        tx = saved_txs.investment[0]
        assert tx.fees == Dezimal("2.50")
        assert tx.retentions == Dezimal("1.00")
        assert tx.order_date is not None

    @pytest.mark.asyncio
    async def test_crypto_missing_symbol(self, client):
        payload = _crypto_tx_payload()
        del payload["symbol"]
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 400
        body = await response.get_json()
        assert "Missing fields" in body["message"]

    @pytest.mark.asyncio
    async def test_crypto_missing_currency_amount(self, client):
        payload = _crypto_tx_payload()
        del payload["currency_amount"]
        response = await client.post(ADD_TX_URL, json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_crypto_tx(
        self, client, entity_port, transaction_port, virtual_import_registry
    ):
        tx_id = uuid.uuid4()
        existing_tx = MagicMock()
        existing_tx.id = tx_id
        existing_tx.source = DataSource.MANUAL
        existing_tx.entity = _make_entity()
        existing_tx.product_type = ProductType.CRYPTO
        transaction_port.get_by_id = AsyncMock(return_value=existing_tx)
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        payload = _crypto_tx_payload(
            name="Buy ETH",
            symbol="ETH",
            currency_amount="1.5",
            price="3500.00",
            fees="3.00",
        )
        response = await client.put(f"{ADD_TX_URL}/{tx_id}", json=payload)
        assert response.status_code == 204

        saved_txs = transaction_port.save.await_args[0][0]
        tx = saved_txs.investment[0]
        assert isinstance(tx, CryptoCurrencyTx)
        assert tx.symbol == "ETH"
        assert tx.currency_amount == Dezimal("1.5")
        assert tx.price == Dezimal("3500.00")
