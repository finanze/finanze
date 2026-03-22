import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    AccountType,
    Accounts,
    EquityType,
    GlobalPosition,
    ManualEntryData,
    ProductType,
    StockDetail,
    StockInvestments,
)
from domain.virtual_data import VirtualDataImport, VirtualDataSource

UPDATE_POSITION_URL = "/api/v1/data/manual/positions"
GET_POSITIONS_URL = "/api/v1/positions"

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


def _account_payload(total="1000.00", currency="EUR", account_type="CHECKING"):
    return {
        "total": total,
        "currency": currency,
        "type": account_type,
    }


def _stock_payload(
    name="ACME Corp",
    ticker="ACME",
    isin="US0000000001",
    shares="10",
    currency="EUR",
    stock_type="STOCK",
    market_value="500",
    initial_investment="450",
    tracker_key="tracker-123",
):
    return {
        "name": name,
        "ticker": ticker,
        "isin": isin,
        "shares": shares,
        "currency": currency,
        "type": stock_type,
        "market_value": market_value,
        "initial_investment": initial_investment,
        "manual_data": {"tracker_key": tracker_key},
    }


def _make_real_position(entity):
    return GlobalPosition(
        id=uuid.uuid4(),
        entity=entity,
        date=datetime.now(tzlocal()),
        products={
            ProductType.ACCOUNT: Accounts(
                [
                    Account(
                        id=uuid.uuid4(),
                        total=Dezimal("50000"),
                        currency="EUR",
                        type=AccountType.CHECKING,
                        name="Real Checking",
                        source=DataSource.REAL,
                    )
                ]
            )
        },
        source=DataSource.REAL,
    )


class TestUpdatePositionValidation:
    @pytest.mark.asyncio
    async def test_returns_400_when_no_entity_id_and_no_name(self, client):
        response = await client.post(
            UPDATE_POSITION_URL,
            json={"products": {}},
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "MISSING_FIELDS"

    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_product_type_field(self, client, entity_port):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "entity_id": ENTITY_ID,
                "products": {
                    "ACCOUNT": [
                        {"currency": "EUR", "type": "CHECKING"},
                    ]
                },
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_404_when_entity_not_found(self, client, entity_port):
        entity_port.get_by_id = AsyncMock(return_value=None)
        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "entity_id": str(uuid.uuid4()),
                "products": {},
            },
        )
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "NOT_FOUND"


class TestCreateNewEntity:
    @pytest.mark.asyncio
    async def test_creates_entity_when_new_entity_name_provided(
        self,
        client,
        entity_port,
        position_port,
        virtual_import_registry,
        manual_position_data_port,
    ):
        entity_port.get_by_name = AsyncMock(return_value=None)
        entity_port.insert = AsyncMock()
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={})

        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "new_entity_name": "My Manual Bank",
                "products": {
                    "ACCOUNT": [_account_payload()],
                },
            },
        )
        assert response.status_code == 204
        entity_port.insert.assert_awaited_once()
        inserted_entity = entity_port.insert.await_args[0][0]
        assert inserted_entity.name == "My Manual Bank"
        assert inserted_entity.origin == EntityOrigin.MANUAL
        position_port.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_409_when_entity_name_already_exists(
        self, client, entity_port
    ):
        entity_port.get_by_name = AsyncMock(return_value=_make_entity())
        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "new_entity_name": "Existing Entity",
                "products": {},
            },
        )
        assert response.status_code == 409
        body = await response.get_json()
        assert body["code"] == "CONFLICT"


class TestCreateAccountPositionAndRead:
    @pytest.mark.asyncio
    async def test_saves_account_position_then_reads_it(
        self,
        client,
        entity_port,
        position_port,
        virtual_import_registry,
        manual_position_data_port,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={})

        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "entity_id": ENTITY_ID,
                "products": {
                    "ACCOUNT": [
                        _account_payload("5000.50", "EUR", "CHECKING"),
                        _account_payload("2000.00", "USD", "SAVINGS"),
                    ],
                },
            },
        )
        assert response.status_code == 204

        position_port.save.assert_awaited_once()
        saved_position = position_port.save.await_args[0][0]
        assert saved_position.source == DataSource.MANUAL
        assert saved_position.entity.id == uuid.UUID(ENTITY_ID)

        accounts = saved_position.products[ProductType.ACCOUNT]
        assert len(accounts.entries) == 2

        # Now read via GET /positions
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={entity: [saved_position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        entity_positions = body["positions"][ENTITY_ID]
        assert len(entity_positions) == 1
        pos = entity_positions[0]
        assert pos["source"] == "MANUAL"
        account_entries = pos["products"]["ACCOUNT"]["entries"]
        assert len(account_entries) == 2
        totals = sorted([a["total"] for a in account_entries])
        assert totals == [2000.0, 5000.5]


class TestCreateStockPositionAndRead:
    @pytest.mark.asyncio
    async def test_saves_stock_position_then_reads_it(
        self,
        client,
        entity_port,
        position_port,
        virtual_import_registry,
        manual_position_data_port,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={})

        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "entity_id": ENTITY_ID,
                "products": {
                    "STOCK_ETF": [_stock_payload()],
                },
            },
        )
        assert response.status_code == 204

        position_port.save.assert_awaited_once()
        manual_position_data_port.save.assert_awaited_once()
        saved_position = position_port.save.await_args[0][0]

        # Read via GET /positions
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={entity: [saved_position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        pos = body["positions"][ENTITY_ID][0]
        stock_entries = pos["products"]["STOCK_ETF"]["entries"]
        assert len(stock_entries) == 1
        stock = stock_entries[0]
        assert stock["name"] == "ACME Corp"
        assert stock["ticker"] == "ACME"
        assert stock["isin"] == "US0000000001"
        assert stock["shares"] == 10.0
        assert stock["market_value"] == 500.0


class TestCoexistenceWithRealData:
    @pytest.mark.asyncio
    async def test_manual_and_real_positions_both_returned(
        self,
        client,
        entity_port,
        position_port,
        virtual_import_registry,
        manual_position_data_port,
    ):
        manual_entity = _make_entity()
        real_entity = _make_entity(REAL_ENTITY_ID, "Real Bank", EntityOrigin.NATIVE)

        entity_port.get_by_id = AsyncMock(return_value=manual_entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={})

        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "entity_id": ENTITY_ID,
                "products": {
                    "ACCOUNT": [_account_payload("3000.00", "EUR", "CHECKING")],
                },
            },
        )
        assert response.status_code == 204

        saved_manual_position = position_port.save.await_args[0][0]
        real_position = _make_real_position(real_entity)

        # GET returns both manual and real
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={
                manual_entity: [saved_manual_position],
                real_entity: [real_position],
            }
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        assert ENTITY_ID in body["positions"]
        assert REAL_ENTITY_ID in body["positions"]

        manual_pos = body["positions"][ENTITY_ID][0]
        assert manual_pos["source"] == "MANUAL"

        real_pos = body["positions"][REAL_ENTITY_ID][0]
        assert real_pos["source"] == "REAL"
        real_accounts = real_pos["products"]["ACCOUNT"]["entries"]
        assert real_accounts[0]["total"] == 50000.0
        assert real_accounts[0]["name"] == "Real Checking"

    @pytest.mark.asyncio
    async def test_real_and_manual_positions_for_same_entity(
        self,
        client,
        entity_port,
        position_port,
        virtual_import_registry,
        manual_position_data_port,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={})

        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "entity_id": ENTITY_ID,
                "products": {
                    "STOCK_ETF": [_stock_payload()],
                },
            },
        )
        assert response.status_code == 204

        saved_manual = position_port.save.await_args[0][0]
        real_position = _make_real_position(entity)

        # Same entity has both a real and manual position
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={entity: [real_position, saved_manual]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        positions_list = body["positions"][ENTITY_ID]
        assert len(positions_list) == 2
        sources = {p["source"] for p in positions_list}
        assert sources == {"REAL", "MANUAL"}


class TestUpdateExistingPositionAndRead:
    @pytest.mark.asyncio
    async def test_same_day_update_replaces_position_and_read_reflects_it(
        self,
        client,
        entity_port,
        position_port,
        virtual_import_registry,
        manual_position_data_port,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)

        now = datetime.now(tzlocal())
        old_position_id = uuid.uuid4()
        import_id = uuid.uuid4()
        prior_import = VirtualDataImport(
            import_id=import_id,
            global_position_id=old_position_id,
            source=VirtualDataSource.MANUAL,
            date=now,
            feature=Feature.POSITION,
            entity_id=uuid.UUID(ENTITY_ID),
        )
        virtual_import_registry.get_last_import_records = AsyncMock(
            return_value=[prior_import]
        )

        old_position = GlobalPosition(
            id=old_position_id,
            entity=entity,
            date=now,
            products={
                ProductType.ACCOUNT: Accounts(
                    [
                        Account(
                            id=uuid.uuid4(),
                            total=Dezimal("1000"),
                            currency="EUR",
                            type=AccountType.CHECKING,
                            source=DataSource.MANUAL,
                        )
                    ]
                )
            },
            source=DataSource.MANUAL,
        )
        position_port.get_by_id = AsyncMock(return_value=old_position)
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={})

        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "entity_id": ENTITY_ID,
                "products": {
                    "ACCOUNT": [_account_payload("9999.99", "EUR", "CHECKING")],
                },
            },
        )
        assert response.status_code == 204

        position_port.delete_by_id.assert_awaited_once_with(old_position_id)
        position_port.save.assert_awaited_once()
        saved_position = position_port.save.await_args[0][0]

        # Verify GET returns updated values
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={entity: [saved_position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        accounts = body["positions"][ENTITY_ID][0]["products"]["ACCOUNT"]["entries"]
        assert len(accounts) == 1
        assert accounts[0]["total"] == 9999.99

    @pytest.mark.asyncio
    async def test_preserves_other_product_types_on_update_and_read(
        self,
        client,
        entity_port,
        position_port,
        virtual_import_registry,
        manual_position_data_port,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)

        now = datetime.now(tzlocal())
        old_position_id = uuid.uuid4()
        import_id = uuid.uuid4()
        prior_import = VirtualDataImport(
            import_id=import_id,
            global_position_id=old_position_id,
            source=VirtualDataSource.MANUAL,
            date=now,
            feature=Feature.POSITION,
            entity_id=uuid.UUID(ENTITY_ID),
        )
        virtual_import_registry.get_last_import_records = AsyncMock(
            return_value=[prior_import]
        )

        old_stock = StockDetail(
            id=uuid.uuid4(),
            name="Old Stock",
            ticker="OLD",
            isin="US9999999999",
            market="NYSE",
            shares=Dezimal("5"),
            initial_investment=Dezimal("200"),
            market_value=Dezimal("250"),
            currency="EUR",
            type=EquityType.STOCK,
            manual_data=ManualEntryData(tracker_key="old-track"),
            source=DataSource.MANUAL,
        )
        old_position = GlobalPosition(
            id=old_position_id,
            entity=entity,
            date=now,
            products={
                ProductType.ACCOUNT: Accounts(
                    [
                        Account(
                            id=uuid.uuid4(),
                            total=Dezimal("1000"),
                            currency="EUR",
                            type=AccountType.CHECKING,
                            source=DataSource.MANUAL,
                        )
                    ]
                ),
                ProductType.STOCK_ETF: StockInvestments([old_stock]),
            },
            source=DataSource.MANUAL,
        )
        position_port.get_by_id = AsyncMock(return_value=old_position)
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={})

        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "entity_id": ENTITY_ID,
                "products": {
                    "ACCOUNT": [_account_payload("7777.00", "EUR", "SAVINGS")],
                },
            },
        )
        assert response.status_code == 204

        saved_position = position_port.save.await_args[0][0]

        # Verify GET shows both preserved stocks and updated accounts
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={entity: [saved_position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        pos = body["positions"][ENTITY_ID][0]
        accounts = pos["products"]["ACCOUNT"]["entries"]
        assert len(accounts) == 1
        stocks = pos["products"]["STOCK_ETF"]["entries"]
        assert len(stocks) == 1
        assert stocks[0]["name"] == "Old Stock"


class TestNewDayImport:
    @pytest.mark.asyncio
    async def test_new_day_creates_new_import_batch(
        self,
        client,
        entity_port,
        position_port,
        virtual_import_registry,
        manual_position_data_port,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)

        yesterday = datetime(2025, 1, 1, 12, 0, tzinfo=tzlocal())
        old_position_id = uuid.uuid4()
        old_import_id = uuid.uuid4()
        other_entity_id = uuid.uuid4()
        other_position_id = uuid.uuid4()

        prior_imports = [
            VirtualDataImport(
                import_id=old_import_id,
                global_position_id=old_position_id,
                source=VirtualDataSource.MANUAL,
                date=yesterday,
                feature=Feature.POSITION,
                entity_id=uuid.UUID(ENTITY_ID),
            ),
            VirtualDataImport(
                import_id=old_import_id,
                global_position_id=other_position_id,
                source=VirtualDataSource.MANUAL,
                date=yesterday,
                feature=Feature.POSITION,
                entity_id=other_entity_id,
            ),
        ]
        virtual_import_registry.get_last_import_records = AsyncMock(
            return_value=prior_imports
        )

        old_position = GlobalPosition(
            id=old_position_id,
            entity=entity,
            date=yesterday,
            products={
                ProductType.ACCOUNT: Accounts(
                    [
                        Account(
                            id=uuid.uuid4(),
                            total=Dezimal("1000"),
                            currency="EUR",
                            type=AccountType.CHECKING,
                            source=DataSource.MANUAL,
                        )
                    ]
                )
            },
            source=DataSource.MANUAL,
        )
        position_port.get_by_id = AsyncMock(return_value=old_position)
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={})

        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "entity_id": ENTITY_ID,
                "products": {
                    "ACCOUNT": [_account_payload("2000.00", "EUR", "CHECKING")],
                },
            },
        )
        assert response.status_code == 204

        position_port.delete_by_id.assert_not_awaited()
        position_port.save.assert_awaited_once()

        virtual_import_registry.insert.assert_awaited_once()
        cloned_entries = virtual_import_registry.insert.await_args[0][0]
        assert len(cloned_entries) == 2
        new_import_id = cloned_entries[0].import_id
        assert all(e.import_id == new_import_id for e in cloned_entries)
        assert new_import_id != old_import_id


class TestMultipleProductTypesAndRead:
    @pytest.mark.asyncio
    async def test_saves_accounts_and_stocks_then_reads_them(
        self,
        client,
        entity_port,
        position_port,
        virtual_import_registry,
        manual_position_data_port,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={})

        response = await client.post(
            UPDATE_POSITION_URL,
            json={
                "entity_id": ENTITY_ID,
                "products": {
                    "ACCOUNT": [
                        _account_payload("3000.00", "EUR", "CHECKING"),
                    ],
                    "STOCK_ETF": [
                        _stock_payload(
                            name="Apple", ticker="AAPL", isin="US0378331005"
                        ),
                    ],
                },
            },
        )
        assert response.status_code == 204

        saved_position = position_port.save.await_args[0][0]
        assert ProductType.ACCOUNT in saved_position.products
        assert ProductType.STOCK_ETF in saved_position.products

        manual_position_data_port.save.assert_awaited_once()

        # Read back via GET /positions
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={entity: [saved_position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        pos = body["positions"][ENTITY_ID][0]
        assert pos["source"] == "MANUAL"
        assert len(pos["products"]["ACCOUNT"]["entries"]) == 1
        assert pos["products"]["ACCOUNT"]["entries"][0]["total"] == 3000.0
        assert len(pos["products"]["STOCK_ETF"]["entries"]) == 1
        assert pos["products"]["STOCK_ETF"]["entries"][0]["name"] == "Apple"
        assert pos["products"]["STOCK_ETF"]["entries"][0]["ticker"] == "AAPL"
