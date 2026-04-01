import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.dezimal import Dezimal
from domain.entity_account import EntityAccount
from domain.entity_login import EntityLoginResult, LoginResultCode
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    FundPortfolio,
    FundPortfolios,
    GlobalPosition,
    InstallmentFrequency,
    InterestType,
    Loan,
    Loans,
    LoanType,
    ProductType,
)
from domain.loan_calculator import LoanCalculationResult
from domain.native_entities import MY_INVESTOR

FETCH_URL = "/api/v1/data/fetch/financial"
MY_INVESTOR_ID = "e0000000-0000-0000-0000-000000000001"
ENTITY_ACCOUNT_ID = "a0000000-0000-0000-0000-000000000001"


def _make_entity_account():
    return EntityAccount(
        id=uuid.UUID(ENTITY_ACCOUNT_ID),
        entity_id=uuid.UUID(MY_INVESTOR_ID),
        created_at=datetime.now(timezone.utc),
    )


def _setup_fetcher(entity_fetchers, entity, login_result, position=None):
    fetcher = MagicMock(spec=FinancialEntityFetcher)
    fetcher.login = AsyncMock(return_value=login_result)
    if position is None:
        position = GlobalPosition(id=uuid.uuid4(), entity=entity, products={})
    fetcher.global_position = AsyncMock(return_value=position)
    fetcher.auto_contributions = AsyncMock(return_value=None)
    fetcher.transactions = AsyncMock(return_value=None)
    entity_fetchers[entity] = fetcher
    return fetcher


def _setup_common(
    entity_account_port, last_fetches_port, credentials_port, sessions_port
):
    entity_account_port.get_by_id = AsyncMock(return_value=_make_entity_account())
    last_fetches_port.get_by_entity_account_id = AsyncMock(return_value=[])
    credentials_port.get = AsyncMock(
        return_value={"user": "myuser", "password": "mypass"}
    )
    sessions_port.get = AsyncMock(return_value=None)


# ---------------------------------------------------------------------------
# Test 1: Stale Reference Migration
# ---------------------------------------------------------------------------


class TestStaleReferenceMigration:
    @pytest.mark.asyncio
    async def test_account_iban_migration_after_fetch(
        self,
        client,
        entity_fetchers,
        credentials_port,
        sessions_port,
        last_fetches_port,
        entity_account_port,
        position_port,
    ):
        """When a fetched position has an account with the same IBAN as an old position
        but a different UUID, migrate_references should be called."""
        _setup_common(
            entity_account_port, last_fetches_port, credentials_port, sessions_port
        )

        old_id = uuid.uuid4()
        new_id = uuid.uuid4()
        iban = "ES1234567890123456789012"

        position = GlobalPosition(
            id=uuid.uuid4(),
            entity=MY_INVESTOR,
            products={
                ProductType.ACCOUNT: Accounts(
                    [
                        Account(
                            id=new_id,
                            total=Dezimal(5000),
                            currency="EUR",
                            type=AccountType.CHECKING,
                            iban=iban,
                            source=DataSource.REAL,
                        )
                    ]
                )
            },
        )
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )

        # Old position had same IBAN but different UUID
        position_port.get_latest_real_position_id = AsyncMock(return_value=uuid.uuid4())
        position_port.get_account_iban_index = AsyncMock(return_value={old_id: iban})
        position_port.get_portfolio_name_index = AsyncMock(return_value={})

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200

        position_port.migrate_references.assert_awaited_once()
        call_args = position_port.migrate_references.await_args
        account_mapping = call_args[0][0]
        assert account_mapping == {old_id: new_id}

    @pytest.mark.asyncio
    async def test_portfolio_name_migration_after_fetch(
        self,
        client,
        entity_fetchers,
        credentials_port,
        sessions_port,
        last_fetches_port,
        entity_account_port,
        position_port,
    ):
        """Same pattern for portfolios matched by name."""
        _setup_common(
            entity_account_port, last_fetches_port, credentials_port, sessions_port
        )

        old_pf_id = uuid.uuid4()
        new_pf_id = uuid.uuid4()
        portfolio_name = "Mi cartera de fondos"

        position = GlobalPosition(
            id=uuid.uuid4(),
            entity=MY_INVESTOR,
            products={
                ProductType.FUND_PORTFOLIO: FundPortfolios(
                    [
                        FundPortfolio(
                            id=new_pf_id,
                            name=portfolio_name,
                            currency="EUR",
                            source=DataSource.REAL,
                        )
                    ]
                )
            },
        )
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )

        position_port.get_latest_real_position_id = AsyncMock(return_value=uuid.uuid4())
        position_port.get_account_iban_index = AsyncMock(return_value={})
        position_port.get_portfolio_name_index = AsyncMock(
            return_value={old_pf_id: portfolio_name}
        )

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200

        position_port.migrate_references.assert_awaited_once()
        call_args = position_port.migrate_references.await_args
        portfolio_mapping = call_args[0][1]
        assert portfolio_mapping == {old_pf_id: new_pf_id}

    @pytest.mark.asyncio
    async def test_no_migration_when_no_old_position(
        self,
        client,
        entity_fetchers,
        credentials_port,
        sessions_port,
        last_fetches_port,
        entity_account_port,
        position_port,
    ):
        """get_latest_real_position_id returns None -> migrate_references not called."""
        _setup_common(
            entity_account_port, last_fetches_port, credentials_port, sessions_port
        )

        iban = "ES9999999999999999999999"
        position = GlobalPosition(
            id=uuid.uuid4(),
            entity=MY_INVESTOR,
            products={
                ProductType.ACCOUNT: Accounts(
                    [
                        Account(
                            id=uuid.uuid4(),
                            total=Dezimal(1000),
                            currency="EUR",
                            type=AccountType.CHECKING,
                            iban=iban,
                            source=DataSource.REAL,
                        )
                    ]
                )
            },
        )
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )

        position_port.get_latest_real_position_id = AsyncMock(return_value=None)

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        position_port.migrate_references.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_migration_when_ids_unchanged(
        self,
        client,
        entity_fetchers,
        credentials_port,
        sessions_port,
        last_fetches_port,
        entity_account_port,
        position_port,
    ):
        """Same UUID on old and new -> no mapping -> migrate_references not called."""
        _setup_common(
            entity_account_port, last_fetches_port, credentials_port, sessions_port
        )

        same_id = uuid.uuid4()
        iban = "ES1111111111111111111111"

        position = GlobalPosition(
            id=uuid.uuid4(),
            entity=MY_INVESTOR,
            products={
                ProductType.ACCOUNT: Accounts(
                    [
                        Account(
                            id=same_id,
                            total=Dezimal(3000),
                            currency="EUR",
                            type=AccountType.CHECKING,
                            iban=iban,
                            source=DataSource.REAL,
                        )
                    ]
                )
            },
        )
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )

        position_port.get_latest_real_position_id = AsyncMock(return_value=uuid.uuid4())
        position_port.get_account_iban_index = AsyncMock(return_value={same_id: iban})
        position_port.get_portfolio_name_index = AsyncMock(return_value={})

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        position_port.migrate_references.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_both_accounts_and_portfolios_migrated(
        self,
        client,
        entity_fetchers,
        credentials_port,
        sessions_port,
        last_fetches_port,
        entity_account_port,
        position_port,
    ):
        """Both account and portfolio changed -> both mappings in call."""
        _setup_common(
            entity_account_port, last_fetches_port, credentials_port, sessions_port
        )

        old_acc_id = uuid.uuid4()
        new_acc_id = uuid.uuid4()
        iban = "ES5555555555555555555555"

        old_pf_id = uuid.uuid4()
        new_pf_id = uuid.uuid4()
        pf_name = "Cartera principal"

        position = GlobalPosition(
            id=uuid.uuid4(),
            entity=MY_INVESTOR,
            products={
                ProductType.ACCOUNT: Accounts(
                    [
                        Account(
                            id=new_acc_id,
                            total=Dezimal(7000),
                            currency="EUR",
                            type=AccountType.CHECKING,
                            iban=iban,
                            source=DataSource.REAL,
                        )
                    ]
                ),
                ProductType.FUND_PORTFOLIO: FundPortfolios(
                    [
                        FundPortfolio(
                            id=new_pf_id,
                            name=pf_name,
                            currency="EUR",
                            source=DataSource.REAL,
                        )
                    ]
                ),
            },
        )
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )

        position_port.get_latest_real_position_id = AsyncMock(return_value=uuid.uuid4())
        position_port.get_account_iban_index = AsyncMock(
            return_value={old_acc_id: iban}
        )
        position_port.get_portfolio_name_index = AsyncMock(
            return_value={old_pf_id: pf_name}
        )

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200

        position_port.migrate_references.assert_awaited_once()
        call_args = position_port.migrate_references.await_args
        account_mapping = call_args[0][0]
        portfolio_mapping = call_args[0][1]
        assert account_mapping == {old_acc_id: new_acc_id}
        assert portfolio_mapping == {old_pf_id: new_pf_id}


# ---------------------------------------------------------------------------
# Test 2: Loan Interest Enrichment
# ---------------------------------------------------------------------------


class TestLoanInterestEnrichment:
    @pytest.mark.asyncio
    async def test_loan_without_interests_gets_enriched(
        self,
        client,
        entity_fetchers,
        credentials_port,
        sessions_port,
        last_fetches_port,
        entity_account_port,
        position_port,
        loan_calculator,
    ):
        """A loan with installment_interests=None triggers calculator, result is set."""
        _setup_common(
            entity_account_port, last_fetches_port, credentials_port, sessions_port
        )

        loan = Loan(
            id=uuid.uuid4(),
            type=LoanType.MORTGAGE,
            currency="EUR",
            current_installment=Dezimal(500),
            interest_rate=Dezimal("0.03"),
            loan_amount=Dezimal(100000),
            creation=date(2020, 1, 15),
            maturity=date(2050, 1, 15),
            principal_outstanding=Dezimal(80000),
            interest_type=InterestType.FIXED,
            installment_frequency=InstallmentFrequency.MONTHLY,
            installment_interests=None,
        )
        position = GlobalPosition(
            id=uuid.uuid4(),
            entity=MY_INVESTOR,
            products={ProductType.LOAN: Loans([loan])},
        )
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )

        loan_calculator.calculate = AsyncMock(
            return_value=LoanCalculationResult(
                current_installment_payment=Dezimal(500),
                current_installment_interests=Dezimal(200),
                principal_outstanding=Dezimal(80000),
                installment_date=None,
            )
        )

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200

        loan_calculator.calculate.assert_awaited_once()
        # The saved position should have the enriched interests
        saved_position = position_port.save.await_args[0][0]
        saved_loan = saved_position.products[ProductType.LOAN].entries[0]
        assert saved_loan.installment_interests == Dezimal(200)

    @pytest.mark.asyncio
    async def test_loan_with_existing_interests_not_recalculated(
        self,
        client,
        entity_fetchers,
        credentials_port,
        sessions_port,
        last_fetches_port,
        entity_account_port,
        position_port,
        loan_calculator,
    ):
        """Loan already has installment_interests -> calculator not called."""
        _setup_common(
            entity_account_port, last_fetches_port, credentials_port, sessions_port
        )

        loan = Loan(
            id=uuid.uuid4(),
            type=LoanType.MORTGAGE,
            currency="EUR",
            current_installment=Dezimal(500),
            interest_rate=Dezimal("0.03"),
            loan_amount=Dezimal(100000),
            creation=date(2020, 1, 15),
            maturity=date(2050, 1, 15),
            principal_outstanding=Dezimal(80000),
            interest_type=InterestType.FIXED,
            installment_frequency=InstallmentFrequency.MONTHLY,
            installment_interests=Dezimal(150),
        )
        position = GlobalPosition(
            id=uuid.uuid4(),
            entity=MY_INVESTOR,
            products={ProductType.LOAN: Loans([loan])},
        )
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        loan_calculator.calculate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_calculator_error_does_not_fail_fetch(
        self,
        client,
        entity_fetchers,
        credentials_port,
        sessions_port,
        last_fetches_port,
        entity_account_port,
        position_port,
        loan_calculator,
    ):
        """Calculator raises -> fetch still returns COMPLETED, interests stay None."""
        _setup_common(
            entity_account_port, last_fetches_port, credentials_port, sessions_port
        )

        loan = Loan(
            id=uuid.uuid4(),
            type=LoanType.MORTGAGE,
            currency="EUR",
            current_installment=Dezimal(500),
            interest_rate=Dezimal("0.03"),
            loan_amount=Dezimal(100000),
            creation=date(2020, 1, 15),
            maturity=date(2050, 1, 15),
            principal_outstanding=Dezimal(80000),
            interest_type=InterestType.FIXED,
            installment_frequency=InstallmentFrequency.MONTHLY,
            installment_interests=None,
        )
        position = GlobalPosition(
            id=uuid.uuid4(),
            entity=MY_INVESTOR,
            products={ProductType.LOAN: Loans([loan])},
        )
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )

        loan_calculator.calculate = AsyncMock(side_effect=Exception("calc boom"))

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"

        # Interests should remain None
        saved_position = position_port.save.await_args[0][0]
        saved_loan = saved_position.products[ProductType.LOAN].entries[0]
        assert saved_loan.installment_interests is None

    @pytest.mark.asyncio
    async def test_no_loans_no_calculator_call(
        self,
        client,
        entity_fetchers,
        credentials_port,
        sessions_port,
        last_fetches_port,
        entity_account_port,
        position_port,
        loan_calculator,
    ):
        """Position with no LOAN product -> calculator not called."""
        _setup_common(
            entity_account_port, last_fetches_port, credentials_port, sessions_port
        )

        position = GlobalPosition(
            id=uuid.uuid4(),
            entity=MY_INVESTOR,
            products={
                ProductType.ACCOUNT: Accounts(
                    [
                        Account(
                            id=uuid.uuid4(),
                            total=Dezimal(2000),
                            currency="EUR",
                            type=AccountType.CHECKING,
                            source=DataSource.REAL,
                        )
                    ]
                )
            },
        )
        _setup_fetcher(
            entity_fetchers,
            MY_INVESTOR,
            EntityLoginResult(code=LoginResultCode.CREATED),
            position=position,
        )

        response = await client.post(
            FETCH_URL,
            json={"entityAccountId": ENTITY_ACCOUNT_ID, "features": ["POSITION"]},
        )
        assert response.status_code == 200
        loan_calculator.calculate.assert_not_awaited()
