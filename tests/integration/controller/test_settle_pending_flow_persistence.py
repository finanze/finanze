"""End-to-end persistence regression tests for settling a pending flow.

These use the REAL position/manual/virtual repositories against the migrated
in-memory DB (created on signup), so they exercise the actual
``get_last_grouped_by_entity`` merge behaviour that previously caused real
products to be duplicated as manual ones when settling.
"""

from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from dateutil.tz import tzlocal

from application.use_cases.manual_position_snapshot import (
    ManualPositionSnapshotWriter,
)
from application.use_cases.settle_pending_flow import SettlePendingFlowImpl
from domain.dezimal import Dezimal
from domain.earnings_expenses import (
    FlowStatus,
    FlowType,
    PendingFlow,
    SettlePendingFlowRequest,
)
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import FlowNotFound, ManualAccountNotFound
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Card,
    Cards,
    CardType,
    GlobalPosition,
    PositionQueryRequest,
    ProductType,
)
from infrastructure.calculations.loan_calculator import LoanCalculator
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.repository.earnings_expenses.pending_flow_repository import (
    PendingFlowRepository,
)
from infrastructure.repository.entity.entity_repository import EntitySQLRepository
from infrastructure.repository.position.manual_position_data_repository import (
    ManualPositionDataSQLRepository,
)
from infrastructure.repository.position.position_repository import (
    PositionSQLRepository,
)
from infrastructure.repository.real_estate.real_estate_repository import (
    RealEstateRepository,
)
from infrastructure.repository.virtual.virtual_import_repository import (
    VirtualImportRepository,
)

SIGNUP_URL = "/api/v1/signup"
USERNAME = "testuser"
PASSWORD = "securePass123"


async def _signup(client):
    response = await client.post(
        SIGNUP_URL, json={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 204


def _make_entity():
    return Entity(
        id=uuid4(),
        name="Cajamar",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _real_position(entity):
    account = Account(
        id=uuid4(),
        total=Dezimal(5000),
        currency="EUR",
        type=AccountType.CHECKING,
        name="Real checking",
        iban="ES1111111111111111111111",
        source=DataSource.REAL,
    )
    card1 = Card(
        id=uuid4(),
        currency="EUR",
        type=CardType.DEBIT,
        used=Dezimal(10),
        related_account=account.id,
        source=DataSource.REAL,
    )
    card2 = Card(
        id=uuid4(),
        currency="EUR",
        type=CardType.CREDIT,
        used=Dezimal(20),
        limit=Dezimal(3000),
        related_account=account.id,
        source=DataSource.REAL,
    )
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        date=datetime.now(tzlocal()),
        products={
            ProductType.ACCOUNT: Accounts([account]),
            ProductType.CARD: Cards([card1, card2]),
        },
        source=DataSource.REAL,
    )


def _manual_position(entity, total=Dezimal(1000)):
    account = Account(
        id=uuid4(),
        total=total,
        currency="EUR",
        type=AccountType.CHECKING,
        name="Manual savings",
        iban="ES2222222222222222222222",
        source=DataSource.MANUAL,
    )
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        date=datetime.now(tzlocal()),
        products={ProductType.ACCOUNT: Accounts([account])},
        source=DataSource.MANUAL,
    )


class _RealStack:
    def __init__(self, db_client):
        self.position_repo = PositionSQLRepository(client=db_client)
        self.manual_data_repo = ManualPositionDataSQLRepository(client=db_client)
        self.virtual_repo = VirtualImportRepository(client=db_client)
        self.real_estate_repo = RealEstateRepository(client=db_client)
        self.pending_repo = PendingFlowRepository(client=db_client)
        self.entity_repo = EntitySQLRepository(client=db_client)
        self.transaction_handler = TransactionHandler(client=db_client)
        self.snapshot_writer = ManualPositionSnapshotWriter(
            position_port=self.position_repo,
            manual_position_data_port=self.manual_data_repo,
            virtual_import_registry=self.virtual_repo,
            real_estate_port=self.real_estate_repo,
            loan_calculator=LoanCalculator(),
        )
        self.settle_uc = SettlePendingFlowImpl(
            pending_flow_port=self.pending_repo,
            position_port=self.position_repo,
            snapshot_writer=self.snapshot_writer,
            exchange_rate_provider=None,
            transaction_handler_port=self.transaction_handler,
        )


@pytest_asyncio.fixture
async def stack(client):
    await _signup(client)
    # db_client is app[1]; reuse the migrated schema.
    from tests.integration.controller.conftest import DBClient  # noqa

    return None


async def _manual_account(stack_obj, entity):
    grouped = await stack_obj.position_repo.get_last_grouped_by_entity(
        PositionQueryRequest(real=False)
    )
    for ent, position in grouped.items():
        if ent.id != entity.id:
            continue
        container = position.products.get(ProductType.ACCOUNT)
        if container and container.entries:
            return position, container.entries[0]
    return None, None


async def _seed(stack_obj, entity, manual_total=Dezimal(1000)):
    await stack_obj.entity_repo.insert(entity)
    await stack_obj.position_repo.save(_real_position(entity))
    await stack_obj.snapshot_writer.write(
        entity, _manual_position(entity, manual_total)
    )


async def _create_flow(stack_obj, amount, flow_type):
    flow = PendingFlow(
        id=None,
        name="Settlement",
        amount=amount,
        currency="EUR",
        flow_type=flow_type,
        category=None,
        status=FlowStatus.ACTIVE,
        date=None,
        icon=None,
    )
    return await stack_obj.pending_repo.save(flow)


class TestSettlePendingFlowPersistence:
    @pytest.mark.asyncio
    async def test_settle_does_not_duplicate_real_products(self, client, app):
        await _signup(client)
        db_client = app[1]
        s = _RealStack(db_client)
        entity = _make_entity()

        await _seed(s, entity, manual_total=Dezimal(1000))
        _, manual_account = await _manual_account(s, entity)
        flow = await _create_flow(s, Dezimal(250), FlowType.EARNING)

        await s.settle_uc.execute(
            SettlePendingFlowRequest(flow_id=flow.id, account_id=manual_account.id)
        )

        # Manual snapshot: exactly one account, no cards copied over.
        manual_grouped = await s.position_repo.get_last_grouped_by_entity(
            PositionQueryRequest(real=False)
        )
        manual_position = next(
            p for e, p in manual_grouped.items() if e.id == entity.id
        )
        manual_accounts = manual_position.products[ProductType.ACCOUNT].entries
        assert len(manual_accounts) == 1
        assert manual_accounts[0].total == Dezimal(1250)
        assert manual_accounts[0].source == DataSource.MANUAL
        card_container = manual_position.products.get(ProductType.CARD)
        assert card_container is None or len(card_container.entries) == 0

        # Real snapshot untouched: one account + two cards, still REAL.
        real_grouped = await s.position_repo.get_last_grouped_by_entity(
            PositionQueryRequest(real=True)
        )
        real_position = next(p for e, p in real_grouped.items() if e.id == entity.id)
        real_accounts = real_position.products[ProductType.ACCOUNT].entries
        assert len(real_accounts) == 1
        assert real_accounts[0].total == Dezimal(5000)
        assert real_accounts[0].source == DataSource.REAL
        assert len(real_position.products[ProductType.CARD].entries) == 2

        # Flow marked completed.
        stored_flow = await s.pending_repo.get_by_id(flow.id)
        assert stored_flow.status == FlowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_expense_subtracts_without_side_effects(self, client, app):
        await _signup(client)
        db_client = app[1]
        s = _RealStack(db_client)
        entity = _make_entity()

        await _seed(s, entity, manual_total=Dezimal(1000))
        _, manual_account = await _manual_account(s, entity)
        flow = await _create_flow(s, Dezimal(400), FlowType.EXPENSE)

        await s.settle_uc.execute(
            SettlePendingFlowRequest(flow_id=flow.id, account_id=manual_account.id)
        )

        manual_grouped = await s.position_repo.get_last_grouped_by_entity(
            PositionQueryRequest(real=False)
        )
        manual_position = next(
            p for e, p in manual_grouped.items() if e.id == entity.id
        )
        manual_accounts = manual_position.products[ProductType.ACCOUNT].entries
        assert len(manual_accounts) == 1
        assert manual_accounts[0].total == Dezimal(600)
        assert manual_position.products.get(ProductType.CARD) is None

    @pytest.mark.asyncio
    async def test_only_target_entity_manual_snapshot_changes(self, client, app):
        await _signup(client)
        db_client = app[1]
        s = _RealStack(db_client)
        target = _make_entity()
        other = _make_entity()
        other.name = "Other"

        await _seed(s, target, manual_total=Dezimal(1000))
        await s.entity_repo.insert(other)
        await s.snapshot_writer.write(other, _manual_position(other, Dezimal(2000)))

        _, target_account = await _manual_account(s, target)
        flow = await _create_flow(s, Dezimal(100), FlowType.EARNING)

        await s.settle_uc.execute(
            SettlePendingFlowRequest(flow_id=flow.id, account_id=target_account.id)
        )

        manual_grouped = await s.position_repo.get_last_grouped_by_entity(
            PositionQueryRequest(real=False)
        )
        target_position = next(
            p for e, p in manual_grouped.items() if e.id == target.id
        )
        other_position = next(p for e, p in manual_grouped.items() if e.id == other.id)
        assert target_position.products[ProductType.ACCOUNT].entries[
            0
        ].total == Dezimal(1100)
        other_accounts = other_position.products[ProductType.ACCOUNT].entries
        assert len(other_accounts) == 1
        assert other_accounts[0].total == Dezimal(2000)

    @pytest.mark.asyncio
    async def test_flow_not_found(self, client, app):
        await _signup(client)
        db_client = app[1]
        s = _RealStack(db_client)
        entity = _make_entity()
        await _seed(s, entity)
        _, manual_account = await _manual_account(s, entity)

        with pytest.raises(FlowNotFound):
            await s.settle_uc.execute(
                SettlePendingFlowRequest(flow_id=uuid4(), account_id=manual_account.id)
            )

    @pytest.mark.asyncio
    async def test_real_account_id_is_rejected(self, client, app):
        await _signup(client)
        db_client = app[1]
        s = _RealStack(db_client)
        entity = _make_entity()
        real_position = _real_position(entity)
        await s.entity_repo.insert(entity)
        await s.position_repo.save(real_position)
        await s.snapshot_writer.write(entity, _manual_position(entity))
        flow = await _create_flow(s, Dezimal(100), FlowType.EARNING)

        real_account_id = real_position.products[ProductType.ACCOUNT].entries[0].id

        with pytest.raises(ManualAccountNotFound):
            await s.settle_uc.execute(
                SettlePendingFlowRequest(flow_id=flow.id, account_id=real_account_id)
            )
