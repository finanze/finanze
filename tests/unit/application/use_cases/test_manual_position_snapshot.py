from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.ports.loan_calculator_port import LoanCalculatorPort
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_position_snapshot import ManualPositionSnapshotWriter
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
    FundDetail,
    FundInvestments,
    FundPortfolio,
    FundPortfolios,
    FundType,
    GlobalPosition,
    InstallmentFrequency,
    InterestType,
    Loan,
    Loans,
    LoanType,
    ProductType,
)


def _make_entity(id=None):
    return Entity(
        id=id or uuid4(),
        name="TestBank",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _make_global_position(products):
    entity = _make_entity()
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        date=datetime.now(tzlocal()),
        products=products,
        source=DataSource.MANUAL,
    )


def _build_writer():
    position_port = AsyncMock(spec=PositionPort)
    manual_data_port = AsyncMock(spec=ManualPositionDataPort)
    virtual_registry = AsyncMock(spec=VirtualImportRegistry)
    real_estate_port = AsyncMock()
    loan_calculator = MagicMock(spec=LoanCalculatorPort)

    writer = ManualPositionSnapshotWriter(
        position_port,
        manual_data_port,
        virtual_registry,
        real_estate_port,
        loan_calculator,
    )
    return writer, real_estate_port


class TestRegenerateSnapshotIds:
    def test_card_related_account_remapped(self):
        acc_id = uuid4()
        account = Account(
            id=acc_id, total=Dezimal(0), currency="EUR", type=AccountType.CHECKING
        )
        card = Card(
            id=uuid4(),
            currency="EUR",
            type=CardType.CREDIT,
            used=Dezimal(0),
            related_account=acc_id,
        )
        position = _make_global_position(
            {
                ProductType.ACCOUNT: Accounts(entries=[account]),
                ProductType.CARD: Cards(entries=[card]),
            }
        )

        old_acc_id = account.id
        ManualPositionSnapshotWriter._regenerate_snapshot_ids(position)

        assert account.id != old_acc_id
        assert card.related_account == account.id

    def test_card_orphan_ref_unchanged(self):
        orphan_id = uuid4()
        card = Card(
            id=uuid4(),
            currency="EUR",
            type=CardType.CREDIT,
            used=Dezimal(0),
            related_account=orphan_id,
        )
        position = _make_global_position(
            {
                ProductType.CARD: Cards(entries=[card]),
            }
        )

        ManualPositionSnapshotWriter._regenerate_snapshot_ids(position)

        assert card.related_account == orphan_id

    def test_fund_portfolio_remapped(self):
        pf_id = uuid4()
        portfolio = FundPortfolio(id=pf_id, name="PF1")
        fund_portfolio_ref = FundPortfolio(id=pf_id, name="PF1")
        fund = FundDetail(
            id=uuid4(),
            name="Fund1",
            isin="XX",
            market=None,
            shares=Dezimal(10),
            market_value=Dezimal(1000),
            currency="EUR",
            type=FundType.MUTUAL_FUND,
            initial_investment=Dezimal(1000),
            portfolio=fund_portfolio_ref,
        )
        position = _make_global_position(
            {
                ProductType.FUND_PORTFOLIO: FundPortfolios(entries=[portfolio]),
                ProductType.FUND: FundInvestments(entries=[fund]),
            }
        )

        old_pf_id = portfolio.id
        ManualPositionSnapshotWriter._regenerate_snapshot_ids(position)

        assert portfolio.id != old_pf_id
        assert fund.portfolio.id == portfolio.id

    def test_fund_orphan_portfolio_unchanged(self):
        orphan_id = uuid4()
        fund_portfolio_ref = FundPortfolio(id=orphan_id, name="Orphan")
        fund = FundDetail(
            id=uuid4(),
            name="Fund1",
            isin="XX",
            market=None,
            shares=Dezimal(10),
            market_value=Dezimal(1000),
            currency="EUR",
            type=FundType.MUTUAL_FUND,
            initial_investment=Dezimal(1000),
            portfolio=fund_portfolio_ref,
        )
        position = _make_global_position(
            {
                ProductType.FUND: FundInvestments(entries=[fund]),
            }
        )

        ManualPositionSnapshotWriter._regenerate_snapshot_ids(position)

        assert fund.portfolio.id == orphan_id

    def test_portfolio_account_id_remapped(self):
        acc_id = uuid4()
        account = Account(
            id=acc_id,
            total=Dezimal(0),
            currency="EUR",
            type=AccountType.FUND_PORTFOLIO,
        )
        portfolio = FundPortfolio(id=uuid4(), name="PF1", account_id=acc_id)
        position = _make_global_position(
            {
                ProductType.ACCOUNT: Accounts(entries=[account]),
                ProductType.FUND_PORTFOLIO: FundPortfolios(entries=[portfolio]),
            }
        )

        old_acc_id = account.id
        ManualPositionSnapshotWriter._regenerate_snapshot_ids(position)

        assert account.id != old_acc_id
        assert portfolio.account_id == account.id

    def test_portfolio_orphan_account_unchanged(self):
        orphan_id = uuid4()
        portfolio = FundPortfolio(id=uuid4(), name="PF1", account_id=orphan_id)
        position = _make_global_position(
            {
                ProductType.FUND_PORTFOLIO: FundPortfolios(entries=[portfolio]),
            }
        )

        ManualPositionSnapshotWriter._regenerate_snapshot_ids(position)

        assert portfolio.account_id == orphan_id

    def test_all_refs_valid_all_remapped(self):
        acc_id = uuid4()
        pf_id = uuid4()
        account = Account(
            id=acc_id,
            total=Dezimal(0),
            currency="EUR",
            type=AccountType.FUND_PORTFOLIO,
        )
        card = Card(
            id=uuid4(),
            currency="EUR",
            type=CardType.CREDIT,
            used=Dezimal(0),
            related_account=acc_id,
        )
        portfolio = FundPortfolio(id=pf_id, name="PF1", account_id=acc_id)
        fund_pf_ref = FundPortfolio(id=pf_id, name="PF1")
        fund = FundDetail(
            id=uuid4(),
            name="Fund1",
            isin="XX",
            market=None,
            shares=Dezimal(10),
            market_value=Dezimal(1000),
            currency="EUR",
            type=FundType.MUTUAL_FUND,
            initial_investment=Dezimal(1000),
            portfolio=fund_pf_ref,
        )
        position = _make_global_position(
            {
                ProductType.ACCOUNT: Accounts(entries=[account]),
                ProductType.CARD: Cards(entries=[card]),
                ProductType.FUND_PORTFOLIO: FundPortfolios(entries=[portfolio]),
                ProductType.FUND: FundInvestments(entries=[fund]),
            }
        )

        old_acc_id = acc_id
        old_pf_id = pf_id
        ManualPositionSnapshotWriter._regenerate_snapshot_ids(position)

        assert account.id != old_acc_id
        assert portfolio.id != old_pf_id
        assert card.related_account == account.id
        assert portfolio.account_id == account.id
        assert fund.portfolio.id == portfolio.id

    def test_no_refs_no_issues(self):
        dep = Deposit(
            id=uuid4(),
            name="Test",
            amount=Dezimal(1000),
            currency="EUR",
            interest_rate=Dezimal("0.03"),
            creation=datetime.now(tzlocal()),
            maturity=datetime.now(tzlocal()).date(),
        )
        position = _make_global_position(
            {
                ProductType.DEPOSIT: Deposits(entries=[dep]),
            }
        )

        old_id = dep.id
        ManualPositionSnapshotWriter._regenerate_snapshot_ids(position)

        assert dep.id != old_id


def _make_loan(id=None):
    return Loan(
        id=id or uuid4(),
        type=LoanType.MORTGAGE,
        currency="EUR",
        current_installment=Dezimal(500),
        interest_rate=Dezimal("0.03"),
        loan_amount=Dezimal(100000),
        creation=datetime.now(tzlocal()).date(),
        maturity=datetime(2050, 1, 15, tzinfo=tzlocal()).date(),
        principal_outstanding=Dezimal(80000),
        interest_type=InterestType.FIXED,
        installment_frequency=InstallmentFrequency.MONTHLY,
    )


class TestSyncLinkedLoanFlows:
    @pytest.mark.asyncio
    async def test_sync_called_for_each_loan(self):
        writer, real_estate_port = _build_writer()
        loan1 = _make_loan()
        loan2 = _make_loan()
        position = _make_global_position(
            {ProductType.LOAN: Loans(entries=[loan1, loan2])}
        )

        await writer._sync_linked_loan_flows(position)

        assert real_estate_port.sync_linked_loan_flows.await_count == 2
        real_estate_port.sync_linked_loan_flows.assert_any_await(loan1)
        real_estate_port.sync_linked_loan_flows.assert_any_await(loan2)

    @pytest.mark.asyncio
    async def test_sync_not_called_when_no_loan_product(self):
        writer, real_estate_port = _build_writer()
        position = _make_global_position({})

        await writer._sync_linked_loan_flows(position)

        real_estate_port.sync_linked_loan_flows.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sync_not_called_when_empty_loans(self):
        writer, real_estate_port = _build_writer()
        position = _make_global_position({ProductType.LOAN: Loans(entries=[])})

        await writer._sync_linked_loan_flows(position)

        real_estate_port.sync_linked_loan_flows.assert_not_awaited()
