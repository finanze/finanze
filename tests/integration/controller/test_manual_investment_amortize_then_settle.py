from datetime import date, datetime
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.use_cases.manual_position_snapshot import (
    ManualPositionSnapshotWriter,
)
from application.use_cases.partial_amortize_manual_investment import (
    PartialAmortizeManualInvestmentImpl,
)
from application.use_cases.settle_manual_investment import (
    SettleManualInvestmentImpl,
)
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import (
    FactoringDetail,
    FactoringInvestments,
    GlobalPosition,
    ProductType,
)
from domain.historic import (
    PartialAmortizeManualInvestmentRequest,
    SettleManualInvestmentRequest,
)
from domain.transactions import TxType
from infrastructure.calculations.loan_calculator import LoanCalculator
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.repository.entity.entity_repository import EntitySQLRepository
from infrastructure.repository.historic.historic_repository import (
    HistoricSQLRepository,
)
from infrastructure.repository.position.manual_position_data_repository import (
    ManualPositionDataSQLRepository,
)
from infrastructure.repository.position.position_repository import (
    PositionSQLRepository,
)
from infrastructure.repository.real_estate.real_estate_repository import (
    RealEstateRepository,
)
from infrastructure.repository.transaction.transaction_repository import (
    TransactionSQLRepository,
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
        name="Manual",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _make_factoring():
    return FactoringDetail(
        id=uuid4(),
        name="Loan A",
        amount=Dezimal("1000"),
        currency="EUR",
        interest_rate=Dezimal("0.1"),
        start=datetime(2024, 1, 1, tzinfo=tzlocal()),
        maturity=date(2024, 12, 31),
        type="SIMPLE",
        state="OUTSTANDING",
        source=DataSource.MANUAL,
    )


def _factoring_position(entity, factoring):
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        date=datetime.now(tzlocal()),
        products={ProductType.FACTORING: FactoringInvestments([factoring])},
        source=DataSource.MANUAL,
    )


@pytest.mark.asyncio
async def test_factoring_settle_repays_pending_after_amortize(client, app):
    await _signup(client)

    db_client = app[1]

    position_port = PositionSQLRepository(client=db_client)
    manual_position_data_port = ManualPositionDataSQLRepository(client=db_client)
    virtual_import_registry = VirtualImportRepository(client=db_client)
    real_estate_repo = RealEstateRepository(client=db_client)
    entity_port = EntitySQLRepository(client=db_client)
    transaction_port = TransactionSQLRepository(client=db_client)
    historic_port = HistoricSQLRepository(client=db_client)
    loan_calculator = LoanCalculator()

    transaction_handler = TransactionHandler(client=db_client)
    snapshot_writer = ManualPositionSnapshotWriter(
        position_port=position_port,
        manual_position_data_port=manual_position_data_port,
        virtual_import_registry=virtual_import_registry,
        real_estate_port=real_estate_repo,
        loan_calculator=loan_calculator,
    )

    entity = _make_entity()
    await entity_port.insert(entity)

    factoring = _make_factoring()
    await snapshot_writer.write(entity, _factoring_position(entity, factoring))

    from application.use_cases.manual_historic_common import load_manual_position

    loaded = await load_manual_position(
        virtual_import_registry, position_port, entity.id
    )
    assert loaded is not None
    container = loaded.products.get(ProductType.FACTORING)
    assert container and container.entries
    persisted_entry_id = container.entries[0].id

    amortize_uc = PartialAmortizeManualInvestmentImpl(
        entity_port=entity_port,
        position_port=position_port,
        transaction_port=transaction_port,
        historic_port=historic_port,
        virtual_import_registry=virtual_import_registry,
        snapshot_writer=snapshot_writer,
        transaction_handler_port=transaction_handler,
    )
    settle_uc = SettleManualInvestmentImpl(
        entity_port=entity_port,
        position_port=position_port,
        transaction_port=transaction_port,
        historic_port=historic_port,
        virtual_import_registry=virtual_import_registry,
        snapshot_writer=snapshot_writer,
        transaction_handler_port=transaction_handler,
    )

    await amortize_uc.execute(
        PartialAmortizeManualInvestmentRequest(
            entity_id=entity.id,
            entry_id=persisted_entry_id,
            product_type=ProductType.FACTORING,
            amount=Dezimal("300"),
            create_investment_tx=False,
        )
    )

    await settle_uc.execute(
        SettleManualInvestmentRequest(
            entity_id=entity.id,
            entry_id=persisted_entry_id,
            product_type=ProductType.FACTORING,
            interests=Dezimal("0"),
            create_investment_tx=False,
        )
    )

    stored = await transaction_port.get_by_entity_and_source(
        entity.id, DataSource.MANUAL
    )
    repayments = [t for t in stored.investment if t.type == TxType.REPAYMENT]
    amounts = sorted(str(t.amount) for t in repayments)

    assert amounts == ["300", "700"]
    assert all(t.amount != Dezimal("1000") for t in repayments)
