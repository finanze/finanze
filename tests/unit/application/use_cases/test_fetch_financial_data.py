from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.ports.loan_calculator_port import LoanCalculatorPort
from application.ports.position_port import PositionPort
from application.use_cases.fetch_financial_data import FetchFinancialDataImpl
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.global_position import (
    Account,
    AccountType,
    Accounts,
    FundPortfolio,
    FundPortfolios,
    GlobalPosition,
    InstallmentFrequency,
    InterestType,
    Loan,
    LoanType,
    Loans,
    ProductType,
)
from domain.loan_calculator import LoanCalculationParams, LoanCalculationResult


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _build_use_case():
    position_port = AsyncMock(spec=PositionPort)
    loan_calculator = AsyncMock(spec=LoanCalculatorPort)

    uc = FetchFinancialDataImpl(
        position_port=position_port,
        auto_contr_port=AsyncMock(),
        transaction_port=AsyncMock(),
        historic_port=AsyncMock(),
        entity_fetchers={},
        config_port=AsyncMock(),
        credentials_port=AsyncMock(),
        sessions_port=AsyncMock(),
        last_fetches_port=AsyncMock(),
        crypto_asset_registry_port=AsyncMock(),
        crypto_asset_info_provider=AsyncMock(),
        transaction_handler_port=MagicMock(),
        keychain_loader=AsyncMock(),
        entity_account_port=AsyncMock(),
        loan_calculator=loan_calculator,
    )
    return uc, position_port, loan_calculator


def _make_entity(id=None):
    return Entity(
        id=id or uuid4(),
        name="Test Entity",
        natural_id="test",
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.NATIVE,
        icon_url=None,
    )


def _make_account(id=None, iban="ES1234"):
    return Account(
        id=id or uuid4(),
        total=Dezimal(1000),
        currency="EUR",
        type=AccountType.CHECKING,
        iban=iban,
    )


def _make_portfolio(id=None, name="Portfolio"):
    return FundPortfolio(
        id=id or uuid4(),
        name=name,
        currency="EUR",
    )


def _make_loan(
    id=None,
    installment_interests=None,
    interest_rate=Dezimal("0.03"),
    interest_type=InterestType.FIXED,
    euribor_rate=None,
    fixed_years=None,
    fixed_interest_rate=None,
    installment_frequency=InstallmentFrequency.MONTHLY,
    creation=date(2020, 1, 15),
    maturity=date(2050, 1, 15),
):
    return Loan(
        id=id or uuid4(),
        type=LoanType.MORTGAGE,
        currency="EUR",
        current_installment=Dezimal(500),
        interest_rate=interest_rate,
        loan_amount=Dezimal(100000),
        creation=creation,
        maturity=maturity,
        principal_outstanding=Dezimal(80000),
        interest_type=interest_type,
        installment_frequency=installment_frequency,
        installment_interests=installment_interests,
        fixed_interest_rate=fixed_interest_rate,
        euribor_rate=euribor_rate,
        fixed_years=fixed_years,
    )


def _make_position(products=None):
    return GlobalPosition(
        id=uuid4(),
        entity=_make_entity(),
        products=products or {},
    )


# ---------------------------------------------------------------------------
# TestMigrateStaleReferences
# ---------------------------------------------------------------------------


class TestMigrateStaleReferences:
    @pytest.mark.asyncio
    async def test_no_old_position_skips(self):
        uc, position_port, _ = _build_use_case()
        position = _make_position()

        await uc._migrate_stale_references(None, position)

        position_port.get_account_iban_index.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_account_iban_match_changed_id(self):
        uc, position_port, _ = _build_use_case()
        old_pos_id = uuid4()
        old_acc_id = uuid4()
        new_acc_id = uuid4()

        position_port.get_account_iban_index.return_value = {old_acc_id: "ES1234"}
        position_port.get_portfolio_name_index.return_value = {}

        new_account = _make_account(id=new_acc_id, iban="ES1234")
        position = _make_position(
            products={ProductType.ACCOUNT: Accounts(entries=[new_account])}
        )

        await uc._migrate_stale_references(old_pos_id, position)

        position_port.migrate_references.assert_awaited_once_with(
            {old_acc_id: new_acc_id}, {}
        )

    @pytest.mark.asyncio
    async def test_portfolio_name_match_changed_id(self):
        uc, position_port, _ = _build_use_case()
        old_pos_id = uuid4()
        old_pf_id = uuid4()
        new_pf_id = uuid4()

        position_port.get_account_iban_index.return_value = {}
        position_port.get_portfolio_name_index.return_value = {old_pf_id: "My PF"}

        new_portfolio = _make_portfolio(id=new_pf_id, name="My PF")
        position = _make_position(
            products={
                ProductType.FUND_PORTFOLIO: FundPortfolios(entries=[new_portfolio])
            }
        )

        await uc._migrate_stale_references(old_pos_id, position)

        position_port.migrate_references.assert_awaited_once_with(
            {}, {old_pf_id: new_pf_id}
        )

    @pytest.mark.asyncio
    async def test_no_matching_ibans_no_migration(self):
        uc, position_port, _ = _build_use_case()
        old_pos_id = uuid4()

        position_port.get_account_iban_index.return_value = {uuid4(): "ES9999"}
        position_port.get_portfolio_name_index.return_value = {}

        new_account = _make_account(iban="ES0000")
        position = _make_position(
            products={ProductType.ACCOUNT: Accounts(entries=[new_account])}
        )

        await uc._migrate_stale_references(old_pos_id, position)

        position_port.migrate_references.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_same_id_same_iban_no_migration(self):
        uc, position_port, _ = _build_use_case()
        old_pos_id = uuid4()
        same_id = uuid4()

        position_port.get_account_iban_index.return_value = {same_id: "ES1234"}
        position_port.get_portfolio_name_index.return_value = {}

        new_account = _make_account(id=same_id, iban="ES1234")
        position = _make_position(
            products={ProductType.ACCOUNT: Accounts(entries=[new_account])}
        )

        await uc._migrate_stale_references(old_pos_id, position)

        position_port.migrate_references.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_partial_account_match(self):
        uc, position_port, _ = _build_use_case()
        old_pos_id = uuid4()
        old_id1, old_id2 = uuid4(), uuid4()
        new_id1 = uuid4()

        position_port.get_account_iban_index.return_value = {
            old_id1: "ES1234",
            old_id2: "ES5678",
        }
        position_port.get_portfolio_name_index.return_value = {}

        new_account = _make_account(id=new_id1, iban="ES1234")
        position = _make_position(
            products={ProductType.ACCOUNT: Accounts(entries=[new_account])}
        )

        await uc._migrate_stale_references(old_pos_id, position)

        position_port.migrate_references.assert_awaited_once_with(
            {old_id1: new_id1}, {}
        )

    @pytest.mark.asyncio
    async def test_both_accounts_and_portfolios_migrated(self):
        uc, position_port, _ = _build_use_case()
        old_pos_id = uuid4()
        old_acc_id, new_acc_id = uuid4(), uuid4()
        old_pf_id, new_pf_id = uuid4(), uuid4()

        position_port.get_account_iban_index.return_value = {old_acc_id: "ES1234"}
        position_port.get_portfolio_name_index.return_value = {old_pf_id: "PF1"}

        new_account = _make_account(id=new_acc_id, iban="ES1234")
        new_portfolio = _make_portfolio(id=new_pf_id, name="PF1")
        position = _make_position(
            products={
                ProductType.ACCOUNT: Accounts(entries=[new_account]),
                ProductType.FUND_PORTFOLIO: FundPortfolios(entries=[new_portfolio]),
            }
        )

        await uc._migrate_stale_references(old_pos_id, position)

        position_port.migrate_references.assert_awaited_once_with(
            {old_acc_id: new_acc_id}, {old_pf_id: new_pf_id}
        )

    @pytest.mark.asyncio
    async def test_old_has_accounts_new_has_none(self):
        uc, position_port, _ = _build_use_case()
        old_pos_id = uuid4()

        position_port.get_account_iban_index.return_value = {uuid4(): "ES1234"}
        position_port.get_portfolio_name_index.return_value = {}

        position = _make_position(products={})

        await uc._migrate_stale_references(old_pos_id, position)

        position_port.migrate_references.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blank_iban_skipped(self):
        uc, position_port, _ = _build_use_case()
        old_pos_id = uuid4()

        position_port.get_account_iban_index.return_value = {uuid4(): "  "}
        position_port.get_portfolio_name_index.return_value = {}

        new_account = _make_account(iban="  ")
        position = _make_position(
            products={ProductType.ACCOUNT: Accounts(entries=[new_account])}
        )

        await uc._migrate_stale_references(old_pos_id, position)

        position_port.migrate_references.assert_not_awaited()


# ---------------------------------------------------------------------------
# TestEnrichLoans
# ---------------------------------------------------------------------------


class TestEnrichLoans:
    @pytest.mark.asyncio
    async def test_missing_interests_enriched(self):
        uc, _, loan_calculator = _build_use_case()
        loan = _make_loan(installment_interests=None)
        result = LoanCalculationResult(
            current_monthly_payment=Dezimal(510),
            current_monthly_interests=Dezimal(200),
            principal_outstanding=Dezimal(79500),
        )
        loan_calculator.calculate.return_value = result
        position = _make_position(products={ProductType.LOAN: Loans(entries=[loan])})

        await uc._enrich_loans(position)

        assert loan.installment_interests == Dezimal(200)
        loan_calculator.calculate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_existing_interests_skipped(self):
        uc, _, loan_calculator = _build_use_case()
        loan = _make_loan(installment_interests=Dezimal(150))
        position = _make_position(products={ProductType.LOAN: Loans(entries=[loan])})

        await uc._enrich_loans(position)

        loan_calculator.calculate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mix_only_missing_enriched(self):
        uc, _, loan_calculator = _build_use_case()
        loan_with = _make_loan(installment_interests=Dezimal(150))
        loan_without = _make_loan(installment_interests=None)
        result = LoanCalculationResult(
            current_monthly_payment=Dezimal(510),
            current_monthly_interests=Dezimal(200),
            principal_outstanding=Dezimal(79500),
        )
        loan_calculator.calculate.return_value = result
        position = _make_position(
            products={ProductType.LOAN: Loans(entries=[loan_with, loan_without])}
        )

        await uc._enrich_loans(position)

        assert loan_calculator.calculate.await_count == 1
        assert loan_without.installment_interests == Dezimal(200)
        assert loan_with.installment_interests == Dezimal(150)

    @pytest.mark.asyncio
    async def test_calculator_exception_swallowed(self):
        uc, _, loan_calculator = _build_use_case()
        loan = _make_loan(installment_interests=None)
        loan_calculator.calculate.side_effect = RuntimeError("boom")
        position = _make_position(products={ProductType.LOAN: Loans(entries=[loan])})

        await uc._enrich_loans(position)

        assert loan.installment_interests is None

    @pytest.mark.asyncio
    async def test_empty_loans_no_calls(self):
        uc, _, loan_calculator = _build_use_case()
        position = _make_position(products={ProductType.LOAN: Loans(entries=[])})

        await uc._enrich_loans(position)

        loan_calculator.calculate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_loan_product_returns_early(self):
        uc, _, loan_calculator = _build_use_case()
        position = _make_position(products={})

        await uc._enrich_loans(position)

        loan_calculator.calculate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_correct_params_passed(self):
        uc, _, loan_calculator = _build_use_case()
        loan = _make_loan(
            interest_rate=Dezimal("0.025"),
            interest_type=InterestType.VARIABLE,
            euribor_rate=Dezimal("0.015"),
            fixed_years=5,
            fixed_interest_rate=Dezimal("0.02"),
            installment_frequency=InstallmentFrequency.QUARTERLY,
            creation=date(2020, 6, 1),
            maturity=date(2045, 6, 1),
        )
        result = LoanCalculationResult(
            current_monthly_payment=Dezimal(510),
            current_monthly_interests=Dezimal(200),
            principal_outstanding=Dezimal(79500),
        )
        loan_calculator.calculate.return_value = result
        position = _make_position(products={ProductType.LOAN: Loans(entries=[loan])})

        await uc._enrich_loans(position)

        expected_params = LoanCalculationParams(
            loan_amount=None,
            interest_rate=loan.interest_rate,
            interest_type=loan.interest_type,
            euribor_rate=loan.euribor_rate,
            fixed_years=loan.fixed_years,
            start=loan.creation,
            end=loan.maturity,
            principal_outstanding=loan.principal_outstanding,
            fixed_interest_rate=loan.fixed_interest_rate,
            installment_frequency=loan.installment_frequency,
        )
        loan_calculator.calculate.assert_awaited_once_with(expected_params)
