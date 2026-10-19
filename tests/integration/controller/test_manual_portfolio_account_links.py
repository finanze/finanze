from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from dateutil.tz import tzlocal

from application.use_cases.manual_historic_common import ManualHistoricWriter
from application.use_cases.manual_position_snapshot import (
    ManualPositionSnapshotWriter,
)
from application.use_cases.update_position import UpdatePositionImpl
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Card,
    Cards,
    CardType,
    Deposit,
    Deposits,
    FundPortfolio,
    FundPortfolios,
    GlobalPosition,
    PositionQueryRequest,
    ProductType,
    UpdatePositionRequest,
)
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
from infrastructure.repository.virtual.virtual_import_repository import (
    VirtualImportRepository,
)

SIGNUP_URL = "/api/v1/signup"


class _Stack:
    def __init__(self, db_client):
        self.position_repo = PositionSQLRepository(client=db_client)
        self.entity_repo = EntitySQLRepository(client=db_client)
        virtual_repo = VirtualImportRepository(client=db_client)
        snapshot_writer = ManualPositionSnapshotWriter(
            position_port=self.position_repo,
            manual_position_data_port=ManualPositionDataSQLRepository(client=db_client),
            virtual_import_registry=virtual_repo,
            real_estate_port=RealEstateRepository(client=db_client),
            loan_calculator=LoanCalculator(),
        )
        self.uc = UpdatePositionImpl(
            entity_port=self.entity_repo,
            position_port=self.position_repo,
            crypto_asset_registry_port=AsyncMock(),
            crypto_asset_info_provider=AsyncMock(),
            transaction_handler_port=TransactionHandler(client=db_client),
            virtual_import_registry=virtual_repo,
            snapshot_writer=snapshot_writer,
            historic_writer=ManualHistoricWriter(
                HistoricSQLRepository(client=db_client)
            ),
        )


@pytest_asyncio.fixture
async def stack(client, db_client):
    response = await client.post(
        SIGNUP_URL, json={"username": "testuser", "password": "securePass123"}
    )
    assert response.status_code == 204
    return _Stack(db_client)


@pytest_asyncio.fixture
async def entity(stack):
    entity = Entity(
        id=uuid4(),
        name="Manual Broker",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )
    await stack.entity_repo.insert(entity)
    return entity


def _account(
    account_id=None,
    total="1000",
    account_type=AccountType.FUND_PORTFOLIO,
    name="Broker cash",
):
    return Account(
        id=account_id,
        total=Dezimal(total),
        currency="EUR",
        type=account_type,
        name=name,
        source=DataSource.MANUAL,
    )


def _portfolio(account_id):
    return FundPortfolio(
        id=None,
        name="Main portfolio",
        currency="EUR",
        account_id=account_id,
        source=DataSource.MANUAL,
    )


def _entries(position, product_type):
    return position.products[product_type].entries


async def _save(stack, entity, products, now=None):
    request = UpdatePositionRequest(
        products=products, entity_id=entity.id, create_investment_txs=False
    )
    if now is None:
        await stack.uc.execute(request)
        return
    with patch("application.use_cases.update_position.datetime") as mock_dt:
        mock_dt.now.return_value = now
        await stack.uc.execute(request)


async def _manual(stack, entity) -> GlobalPosition:
    grouped = await stack.position_repo.get_last_grouped_by_entity(
        PositionQueryRequest(entities=[entity.id], real=False)
    )
    return next(p for e, p in grouped.items() if e.id == entity.id)


async def _seed_linked(stack, entity):
    await _save(stack, entity, {ProductType.ACCOUNT: Accounts([_account()])})
    [account] = _entries(await _manual(stack, entity), ProductType.ACCOUNT)
    await _save(
        stack,
        entity,
        {ProductType.FUND_PORTFOLIO: FundPortfolios([_portfolio(account.id)])},
    )
    return await _manual(stack, entity)


def _tomorrow():
    return datetime.now(tzlocal()) + timedelta(days=1)


class TestManualPortfolioAccountLink:
    @pytest.mark.asyncio
    async def test_read_exposes_linked_account_id(self, stack, entity):
        position = await _seed_linked(stack, entity)

        [account] = _entries(position, ProductType.ACCOUNT)
        [portfolio] = _entries(position, ProductType.FUND_PORTFOLIO)
        assert portfolio.account_id == account.id
        assert portfolio.account.id == account.id
        assert portfolio.account.name == "Broker cash"
        assert portfolio.account.total == Dezimal("1000")
        assert portfolio.account.currency == "EUR"
        assert portfolio.account.type == AccountType.FUND_PORTFOLIO
        assert portfolio.account.source == DataSource.MANUAL

    @pytest.mark.asyncio
    @pytest.mark.parametrize("next_day", [False, True])
    async def test_account_only_save_keeps_link(self, stack, entity, next_day):
        before = await _seed_linked(stack, entity)
        [old_account] = _entries(before, ProductType.ACCOUNT)
        [old_portfolio] = _entries(before, ProductType.FUND_PORTFOLIO)

        await _save(
            stack,
            entity,
            {ProductType.ACCOUNT: Accounts([_account(old_account.id, "2500")])},
            now=_tomorrow() if next_day else None,
        )

        after = await _manual(stack, entity)
        [account] = _entries(after, ProductType.ACCOUNT)
        [portfolio] = _entries(after, ProductType.FUND_PORTFOLIO)
        assert account.total == Dezimal("2500")
        assert account.id != old_account.id
        assert portfolio.account_id == account.id
        assert portfolio.account.id == account.id
        assert portfolio.account.total == Dezimal("2500")

        if next_day:
            previous = await stack.position_repo.get_by_id(before.id)
            [prev_portfolio] = _entries(previous, ProductType.FUND_PORTFOLIO)
            assert prev_portfolio.id == old_portfolio.id
            assert prev_portfolio.account_id == old_account.id

    @pytest.mark.asyncio
    async def test_card_linked_to_same_account_keeps_link(self, stack, entity):
        before = await _seed_linked(stack, entity)
        [old_account] = _entries(before, ProductType.ACCOUNT)

        await _save(
            stack,
            entity,
            {
                ProductType.ACCOUNT: Accounts([_account(old_account.id)]),
                ProductType.CARD: Cards(
                    [
                        Card(
                            id=None,
                            currency="EUR",
                            type=CardType.DEBIT,
                            used=Dezimal(0),
                            related_account=old_account.id,
                            source=DataSource.MANUAL,
                        )
                    ]
                ),
            },
        )

        after = await _manual(stack, entity)
        [account] = _entries(after, ProductType.ACCOUNT)
        [card] = _entries(after, ProductType.CARD)
        [portfolio] = _entries(after, ProductType.FUND_PORTFOLIO)
        assert card.related_account == account.id
        assert portfolio.account_id == account.id

    @pytest.mark.asyncio
    async def test_unrelated_product_save_keeps_link(self, stack, entity):
        await _seed_linked(stack, entity)

        await _save(
            stack,
            entity,
            {
                ProductType.DEPOSIT: Deposits(
                    [
                        Deposit(
                            id=None,
                            name="Term deposit",
                            amount=Dezimal(5000),
                            currency="EUR",
                            interest_rate=Dezimal("0.02"),
                            creation=datetime.now(tzlocal()),
                            maturity=date.today() + timedelta(days=365),
                            source=DataSource.MANUAL,
                        )
                    ]
                )
            },
        )

        after = await _manual(stack, entity)
        [account] = _entries(after, ProductType.ACCOUNT)
        [portfolio] = _entries(after, ProductType.FUND_PORTFOLIO)
        assert len(_entries(after, ProductType.DEPOSIT)) == 1
        assert portfolio.account_id == account.id

    @pytest.mark.asyncio
    @pytest.mark.parametrize("next_day", [False, True])
    async def test_removing_linked_account_unlinks_portfolio(
        self, stack, entity, next_day
    ):
        before = await _seed_linked(stack, entity)
        [old_portfolio] = _entries(before, ProductType.FUND_PORTFOLIO)

        await _save(
            stack,
            entity,
            {
                ProductType.ACCOUNT: Accounts(
                    [_account(account_type=AccountType.CHECKING, name="Checking")]
                )
            },
            now=_tomorrow() if next_day else None,
        )

        after = await _manual(stack, entity)
        [account] = _entries(after, ProductType.ACCOUNT)
        [portfolio] = _entries(after, ProductType.FUND_PORTFOLIO)
        assert account.name == "Checking"
        assert portfolio.name == old_portfolio.name
        assert portfolio.account_id is None
        assert portfolio.account is None

    @pytest.mark.asyncio
    async def test_link_to_real_account_survives_manual_account_save(
        self, stack, entity
    ):
        real_account_id = uuid4()
        await stack.position_repo.save(
            GlobalPosition(
                id=uuid4(),
                entity=entity,
                date=datetime.now(tzlocal()),
                products={
                    ProductType.ACCOUNT: Accounts(
                        [
                            Account(
                                id=real_account_id,
                                total=Dezimal(300),
                                currency="EUR",
                                type=AccountType.FUND_PORTFOLIO,
                                name="Real cash",
                                source=DataSource.REAL,
                            )
                        ]
                    )
                },
                source=DataSource.REAL,
            )
        )
        await _save(
            stack,
            entity,
            {ProductType.FUND_PORTFOLIO: FundPortfolios([_portfolio(real_account_id)])},
        )

        await _save(
            stack,
            entity,
            {
                ProductType.ACCOUNT: Accounts(
                    [_account(account_type=AccountType.CHECKING, name="Checking")]
                )
            },
        )

        after = await _manual(stack, entity)
        [portfolio] = _entries(after, ProductType.FUND_PORTFOLIO)
        assert portfolio.account_id == real_account_id
        assert portfolio.account.name == "Real cash"
