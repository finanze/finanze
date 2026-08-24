from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from dateutil.tz import tzlocal
import pytest

from application.ports.loan_calculator_port import LoanCalculatorPort
from application.ports.position_port import PositionPort
from application.use_cases.fetch_financial_data import FetchFinancialDataImpl
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.entity_account import EntityAccount
from domain.entity_login import EntityLoginResult, EntitySession, LoginResultCode
from domain.fetch_record import DataSource, FetchRecord
from domain.fetch_result import FetchOptions, FetchRequest, FetchResultCode
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
from domain.native_entities import TRADE_REPUBLIC, URBANITAE
from domain.public_keychain import PublicKeychain
from domain.transactions import AccountTx, Transactions, TxType


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _build_use_case():
    position_port = AsyncMock(spec=PositionPort)
    loan_calculator = AsyncMock(spec=LoanCalculatorPort)

    real_estate_port = AsyncMock()

    transaction_handler_port = MagicMock()
    tx_ctx = MagicMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=None)
    tx_ctx.__aexit__ = AsyncMock(return_value=None)
    transaction_handler_port.start = MagicMock(return_value=tx_ctx)

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
        transaction_handler_port=transaction_handler_port,
        keychain_loader=AsyncMock(),
        entity_account_port=AsyncMock(),
        loan_calculator=loan_calculator,
        real_estate_port=real_estate_port,
        feature_flag_port=MagicMock(get_all=MagicMock(return_value={})),
    )
    return uc, position_port, loan_calculator, real_estate_port


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
        uc, position_port, _, _ = _build_use_case()
        position = _make_position()

        await uc._migrate_stale_references(None, position)

        position_port.get_account_iban_index.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_account_iban_match_changed_id(self):
        uc, position_port, _, _ = _build_use_case()
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
        uc, position_port, _, _ = _build_use_case()
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
        uc, position_port, _, _ = _build_use_case()
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
        uc, position_port, _, _ = _build_use_case()
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
        uc, position_port, _, _ = _build_use_case()
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
        uc, position_port, _, _ = _build_use_case()
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
        uc, position_port, _, _ = _build_use_case()
        old_pos_id = uuid4()

        position_port.get_account_iban_index.return_value = {uuid4(): "ES1234"}
        position_port.get_portfolio_name_index.return_value = {}

        position = _make_position(products={})

        await uc._migrate_stale_references(old_pos_id, position)

        position_port.migrate_references.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blank_iban_skipped(self):
        uc, position_port, _, _ = _build_use_case()
        old_pos_id = uuid4()

        position_port.get_account_iban_index.return_value = {uuid4(): "  "}
        position_port.get_portfolio_name_index.return_value = {}

        new_account = _make_account(iban="  ")
        position = _make_position(
            products={ProductType.ACCOUNT: Accounts(entries=[new_account])}
        )

        await uc._migrate_stale_references(old_pos_id, position)

        position_port.migrate_references.assert_not_awaited()


class TestExecute:
    def test_fetch_lock_is_scoped_to_entity_account(self):
        uc, _, _, _ = _build_use_case()
        first_account_id = uuid4()
        second_account_id = uuid4()

        assert uc._get_lock(first_account_id) is not uc._get_lock(second_account_id)
        assert uc._get_lock(first_account_id) is uc._get_lock(first_account_id)

    @pytest.mark.asyncio
    async def test_login_required_clears_stored_session(self):
        uc, _, _, _ = _build_use_case()
        account_id = uuid4()
        account = EntityAccount(
            id=account_id,
            entity_id=TRADE_REPUBLIC.id,
            created_at=datetime.now(tzlocal()),
        )
        fetcher = AsyncMock()
        fetcher.login.return_value = EntityLoginResult(LoginResultCode.LOGIN_REQUIRED)

        uc._entity_account_port.get_by_id.return_value = account
        uc._last_fetches_port.get_by_entity_account_id.return_value = []
        uc._credentials_port.get.return_value = {
            "phone": "+49123456789",
            "password": "1234",
        }
        uc._sessions_port.get.return_value = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload={"cookies": []},
        )
        uc._keychain_loader.load.return_value = PublicKeychain({})
        uc._entity_fetchers[TRADE_REPUBLIC] = fetcher

        result = await uc.execute(
            FetchRequest(
                entity_account_id=account_id,
                features=[Feature.POSITION],
            )
        )

        assert result.code == FetchResultCode.LOGIN_REQUIRED
        uc._sessions_port.delete.assert_awaited_once_with(account_id)
        uc._credentials_port.update_expiration.assert_awaited_once()


# ---------------------------------------------------------------------------
# TestEnrichLoans
# ---------------------------------------------------------------------------


class TestEnrichLoans:
    @pytest.mark.asyncio
    async def test_missing_interests_enriched(self):
        uc, _, loan_calculator, _ = _build_use_case()
        loan = _make_loan(installment_interests=None)
        result = LoanCalculationResult(
            current_installment_payment=Dezimal(510),
            current_installment_interests=Dezimal(200),
            principal_outstanding=Dezimal(79500),
        )
        loan_calculator.calculate.return_value = result
        position = _make_position(products={ProductType.LOAN: Loans(entries=[loan])})

        await uc._enrich_loans(position)

        assert loan.installment_interests == Dezimal(200)
        loan_calculator.calculate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_existing_interests_skipped(self):
        uc, _, loan_calculator, _ = _build_use_case()
        loan = _make_loan(installment_interests=Dezimal(150))
        position = _make_position(products={ProductType.LOAN: Loans(entries=[loan])})

        await uc._enrich_loans(position)

        loan_calculator.calculate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mix_only_missing_enriched(self):
        uc, _, loan_calculator, _ = _build_use_case()
        loan_with = _make_loan(installment_interests=Dezimal(150))
        loan_without = _make_loan(installment_interests=None)
        result = LoanCalculationResult(
            current_installment_payment=Dezimal(510),
            current_installment_interests=Dezimal(200),
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
        uc, _, loan_calculator, _ = _build_use_case()
        loan = _make_loan(installment_interests=None)
        loan_calculator.calculate.side_effect = RuntimeError("boom")
        position = _make_position(products={ProductType.LOAN: Loans(entries=[loan])})

        await uc._enrich_loans(position)

        assert loan.installment_interests is None

    @pytest.mark.asyncio
    async def test_empty_loans_no_calls(self):
        uc, _, loan_calculator, _ = _build_use_case()
        position = _make_position(products={ProductType.LOAN: Loans(entries=[])})

        await uc._enrich_loans(position)

        loan_calculator.calculate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_loan_product_returns_early(self):
        uc, _, loan_calculator, _ = _build_use_case()
        position = _make_position(products={})

        await uc._enrich_loans(position)

        loan_calculator.calculate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_correct_params_passed(self):
        uc, _, loan_calculator, _ = _build_use_case()
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
            current_installment_payment=Dezimal(510),
            current_installment_interests=Dezimal(200),
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


# ---------------------------------------------------------------------------
# TestSyncLinkedLoanFlows
# ---------------------------------------------------------------------------


class TestSyncLinkedLoanFlows:
    @pytest.mark.asyncio
    async def test_sync_called_for_each_loan(self):
        uc, _, _, real_estate_port = _build_use_case()
        loan1 = _make_loan()
        loan2 = _make_loan()
        position = _make_position(
            products={ProductType.LOAN: Loans(entries=[loan1, loan2])}
        )

        await uc._sync_linked_loan_flows(position)

        assert real_estate_port.sync_linked_loan_flows.await_count == 2
        real_estate_port.sync_linked_loan_flows.assert_any_await(loan1)
        real_estate_port.sync_linked_loan_flows.assert_any_await(loan2)

    @pytest.mark.asyncio
    async def test_sync_not_called_when_no_loan_product(self):
        uc, _, _, real_estate_port = _build_use_case()
        position = _make_position(products={})

        await uc._sync_linked_loan_flows(position)

        real_estate_port.sync_linked_loan_flows.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sync_not_called_when_empty_loans(self):
        uc, _, _, real_estate_port = _build_use_case()
        position = _make_position(products={ProductType.LOAN: Loans(entries=[])})

        await uc._sync_linked_loan_flows(position)

        real_estate_port.sync_linked_loan_flows.assert_not_awaited()


def _saved_features(uc):
    features = []
    for call in uc._last_fetches_port.save.await_args_list:
        for record in call.args[0]:
            features.append(record.feature)
    return features


def _make_account_tx(entity):
    return AccountTx(
        id=uuid4(),
        ref="TX-001",
        name="Transfer",
        amount=Dezimal("100"),
        currency="EUR",
        type=TxType.TRANSFER_IN,
        date=datetime.now(tzlocal()),
        entity=entity,
        source=DataSource.REAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal("0"),
        retentions=Dezimal("0"),
    )


class TestIsolatedFeaturePersist:
    @pytest.mark.asyncio
    async def test_position_saved_when_transactions_fail(self):
        uc, position_port, _, _ = _build_use_case()
        entity = TRADE_REPUBLIC
        position = _make_position()
        fetcher = AsyncMock()
        fetcher.global_position = AsyncMock(return_value=position)
        fetcher.transactions = AsyncMock(side_effect=RuntimeError("txs boom"))
        uc._transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        position_port.get_latest_real_position_id = AsyncMock(return_value=None)
        account_id = uuid4()

        result = await uc.get_data(
            entity,
            [Feature.POSITION, Feature.TRANSACTIONS],
            fetcher,
            FetchOptions(),
            account_id,
        )

        assert result.code == FetchResultCode.PARTIALLY_COMPLETED
        assert result.details["failedFeatures"] == [Feature.TRANSACTIONS.value]
        assert result.details["completedFeatures"] == [Feature.POSITION.value]
        position_port.save.assert_awaited_once_with(position)
        uc._transaction_port.save.assert_not_awaited()
        uc._transaction_port.delete_by_entity_account_id.assert_not_awaited()
        assert _saved_features(uc) == [Feature.POSITION]

    @pytest.mark.asyncio
    async def test_transactions_saved_when_position_fails(self):
        uc, position_port, _, _ = _build_use_case()
        entity = TRADE_REPUBLIC
        txs = Transactions(account=[_make_account_tx(entity)], investment=[])
        fetcher = AsyncMock()
        fetcher.global_position = AsyncMock(side_effect=RuntimeError("pos boom"))
        fetcher.transactions = AsyncMock(return_value=txs)
        uc._transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        account_id = uuid4()

        result = await uc.get_data(
            entity,
            [Feature.POSITION, Feature.TRANSACTIONS],
            fetcher,
            FetchOptions(),
            account_id,
        )

        assert result.code == FetchResultCode.PARTIALLY_COMPLETED
        assert result.details["failedFeatures"] == [Feature.POSITION.value]
        assert result.details["completedFeatures"] == [Feature.TRANSACTIONS.value]
        position_port.save.assert_not_awaited()
        uc._transaction_port.save.assert_awaited_once_with(txs)
        assert _saved_features(uc) == [Feature.TRANSACTIONS]

    @pytest.mark.asyncio
    async def test_auto_contributions_fail_does_not_block_position(self):
        uc, position_port, _, _ = _build_use_case()
        entity = TRADE_REPUBLIC
        position = _make_position()
        fetcher = AsyncMock()
        fetcher.global_position = AsyncMock(return_value=position)
        fetcher.auto_contributions = AsyncMock(side_effect=RuntimeError("contrib boom"))
        position_port.get_latest_real_position_id = AsyncMock(return_value=None)
        account_id = uuid4()

        result = await uc.get_data(
            entity,
            [Feature.POSITION, Feature.AUTO_CONTRIBUTIONS],
            fetcher,
            FetchOptions(),
            account_id,
        )

        assert result.code == FetchResultCode.PARTIALLY_COMPLETED
        assert result.details["failedFeatures"] == [Feature.AUTO_CONTRIBUTIONS.value]
        assert result.details["completedFeatures"] == [Feature.POSITION.value]
        position_port.save.assert_awaited_once_with(position)
        uc._auto_contr_repository.save.assert_not_awaited()
        assert _saved_features(uc) == [Feature.POSITION]

    @pytest.mark.asyncio
    async def test_historic_fail_keeps_saved_transactions(self):
        uc, _, _, _ = _build_use_case()
        entity = URBANITAE
        txs = Transactions(account=[_make_account_tx(entity)], investment=[])
        fetcher = AsyncMock()
        fetcher.transactions = AsyncMock(return_value=txs)
        fetcher.historical_position = AsyncMock(side_effect=RuntimeError("hist boom"))
        uc._transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        account_id = uuid4()

        result = await uc.get_data(
            entity,
            [Feature.TRANSACTIONS, Feature.HISTORIC],
            fetcher,
            FetchOptions(),
            account_id,
        )

        assert result.code == FetchResultCode.PARTIALLY_COMPLETED
        assert result.details["failedFeatures"] == [Feature.HISTORIC.value]
        assert result.details["completedFeatures"] == [Feature.TRANSACTIONS.value]
        uc._transaction_port.save.assert_awaited_once_with(txs)
        uc._historic_port.save.assert_not_awaited()
        uc._historic_port.delete_by_entity_account_id.assert_not_awaited()
        assert _saved_features(uc) == [Feature.TRANSACTIONS]

    @pytest.mark.asyncio
    async def test_all_units_fail_reraises(self):
        uc, position_port, _, _ = _build_use_case()
        entity = TRADE_REPUBLIC
        fetcher = AsyncMock()
        fetcher.global_position = AsyncMock(side_effect=RuntimeError("pos boom"))
        fetcher.transactions = AsyncMock(side_effect=RuntimeError("txs boom"))
        uc._transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        account_id = uuid4()

        with pytest.raises(RuntimeError, match="txs boom"):
            await uc.get_data(
                entity,
                [Feature.POSITION, Feature.TRANSACTIONS],
                fetcher,
                FetchOptions(),
                account_id,
            )

        position_port.save.assert_not_awaited()
        uc._transaction_port.save.assert_not_awaited()
        uc._last_fetches_port.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deep_delete_skipped_when_transactions_fail(self):
        uc, position_port, _, _ = _build_use_case()
        entity = TRADE_REPUBLIC
        position = _make_position()
        fetcher = AsyncMock()
        fetcher.global_position = AsyncMock(return_value=position)
        fetcher.transactions = AsyncMock(side_effect=RuntimeError("txs boom"))
        position_port.get_latest_real_position_id = AsyncMock(return_value=None)
        account_id = uuid4()

        result = await uc.get_data(
            entity,
            [Feature.POSITION, Feature.TRANSACTIONS],
            fetcher,
            FetchOptions(deep=True),
            account_id,
        )

        assert result.code == FetchResultCode.PARTIALLY_COMPLETED
        uc._transaction_port.delete_by_entity_account_id.assert_not_awaited()
        uc._transaction_port.get_refs_by_entity_account.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_historic_skipped_when_transactions_fail(self):
        uc, _, _, _ = _build_use_case()
        entity = URBANITAE
        fetcher = AsyncMock()
        fetcher.transactions = AsyncMock(side_effect=RuntimeError("txs boom"))
        uc._transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        account_id = uuid4()

        with pytest.raises(RuntimeError, match="txs boom"):
            await uc.get_data(
                entity,
                [Feature.TRANSACTIONS, Feature.HISTORIC],
                fetcher,
                FetchOptions(),
                account_id,
            )

        fetcher.historical_position.assert_not_awaited()
        uc._historic_port.save.assert_not_awaited()
        fetcher.close.assert_awaited_once()


class TestFetcherCloseAfterFeatures:
    @pytest.mark.asyncio
    async def test_close_once_after_all_requested_features(self):
        uc, position_port, _, _ = _build_use_case()
        entity = TRADE_REPUBLIC
        position = _make_position()
        txs = Transactions(account=[_make_account_tx(entity)], investment=[])
        fetcher = AsyncMock()
        fetcher.global_position = AsyncMock(return_value=position)
        fetcher.auto_contributions = AsyncMock(return_value=None)
        fetcher.transactions = AsyncMock(return_value=txs)
        uc._transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        position_port.get_latest_real_position_id = AsyncMock(return_value=None)
        account_id = uuid4()

        result = await uc.get_data(
            entity,
            [Feature.POSITION, Feature.AUTO_CONTRIBUTIONS, Feature.TRANSACTIONS],
            fetcher,
            FetchOptions(),
            account_id,
        )

        assert result.code == FetchResultCode.COMPLETED
        fetcher.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_after_partial_failure(self):
        uc, position_port, _, _ = _build_use_case()
        entity = TRADE_REPUBLIC
        position = _make_position()
        fetcher = AsyncMock()
        fetcher.global_position = AsyncMock(return_value=position)
        fetcher.transactions = AsyncMock(side_effect=RuntimeError("txs boom"))
        uc._transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        position_port.get_latest_real_position_id = AsyncMock(return_value=None)
        account_id = uuid4()

        result = await uc.get_data(
            entity,
            [Feature.POSITION, Feature.TRANSACTIONS],
            fetcher,
            FetchOptions(),
            account_id,
        )

        assert result.code == FetchResultCode.PARTIALLY_COMPLETED
        fetcher.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_when_all_features_fail(self):
        uc, _, _, _ = _build_use_case()
        entity = TRADE_REPUBLIC
        fetcher = AsyncMock()
        fetcher.global_position = AsyncMock(side_effect=RuntimeError("pos boom"))
        fetcher.transactions = AsyncMock(side_effect=RuntimeError("txs boom"))
        uc._transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())
        account_id = uuid4()

        with pytest.raises(RuntimeError, match="txs boom"):
            await uc.get_data(
                entity,
                [Feature.POSITION, Feature.TRANSACTIONS],
                fetcher,
                FetchOptions(),
                account_id,
            )

        fetcher.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_error_does_not_hide_feature_error(self):
        uc, _, _, _ = _build_use_case()
        entity = TRADE_REPUBLIC
        fetcher = AsyncMock()
        fetcher.global_position = AsyncMock(side_effect=RuntimeError("pos boom"))
        fetcher.close = AsyncMock(side_effect=RuntimeError("close boom"))
        account_id = uuid4()

        with pytest.raises(RuntimeError, match="pos boom"):
            await uc.get_data(
                entity,
                [Feature.POSITION],
                fetcher,
                FetchOptions(),
                account_id,
            )

        fetcher.close.assert_awaited_once()


async def _prepare_logged_in_execute(uc, entity, account_id, last_fetches=None):
    account = EntityAccount(
        id=account_id,
        entity_id=entity.id,
        created_at=datetime.now(tzlocal()),
    )
    fetcher = AsyncMock()
    fetcher.login.return_value = EntityLoginResult(LoginResultCode.RESUMED)
    uc._entity_account_port.get_by_id.return_value = account
    uc._last_fetches_port.get_by_entity_account_id.return_value = last_fetches or []
    uc._credentials_port.get.return_value = {
        "phone": "+49123456789",
        "password": "1234",
    }
    uc._sessions_port.get.return_value = None
    uc._keychain_loader.load.return_value = PublicKeychain({})
    uc._entity_fetchers[entity] = fetcher
    return fetcher


class TestPerFeatureCooldown:
    @pytest.mark.asyncio
    async def test_mixed_cooldown_fetches_pending_feature_only(self):
        uc, position_port, _, _ = _build_use_case()
        account_id = uuid4()
        txs = Transactions(account=[_make_account_tx(TRADE_REPUBLIC)], investment=[])
        recent = FetchRecord(
            entity_id=TRADE_REPUBLIC.id,
            feature=Feature.POSITION,
            date=datetime.now(tzlocal()),
            entity_account_id=account_id,
        )
        stale = FetchRecord(
            entity_id=TRADE_REPUBLIC.id,
            feature=Feature.TRANSACTIONS,
            date=datetime.now(tzlocal()) - timedelta(minutes=10),
            entity_account_id=account_id,
        )
        fetcher = await _prepare_logged_in_execute(
            uc, TRADE_REPUBLIC, account_id, last_fetches=[recent, stale]
        )
        fetcher.transactions = AsyncMock(return_value=txs)
        uc._transaction_port.get_refs_by_entity_account = AsyncMock(return_value=set())

        result = await uc.execute(
            FetchRequest(
                entity_account_id=account_id,
                features=[Feature.POSITION, Feature.TRANSACTIONS],
            )
        )

        assert result.code == FetchResultCode.COMPLETED
        fetcher.global_position.assert_not_awaited()
        fetcher.transactions.assert_awaited_once()
        position_port.save.assert_not_awaited()
        uc._transaction_port.save.assert_awaited_once_with(txs)
        assert result.details["completedFeatures"] == [Feature.TRANSACTIONS.value]
        assert "failedFeatures" not in result.details

    @pytest.mark.asyncio
    async def test_all_requested_features_cooled_skips_login(self):
        uc, _, _, _ = _build_use_case()
        account_id = uuid4()
        recent_pos = FetchRecord(
            entity_id=TRADE_REPUBLIC.id,
            feature=Feature.POSITION,
            date=datetime.now(tzlocal()),
            entity_account_id=account_id,
        )
        recent_txs = FetchRecord(
            entity_id=TRADE_REPUBLIC.id,
            feature=Feature.TRANSACTIONS,
            date=datetime.now(tzlocal()),
            entity_account_id=account_id,
        )
        fetcher = await _prepare_logged_in_execute(
            uc, TRADE_REPUBLIC, account_id, last_fetches=[recent_pos, recent_txs]
        )

        result = await uc.execute(
            FetchRequest(
                entity_account_id=account_id,
                features=[Feature.POSITION, Feature.TRANSACTIONS],
            )
        )

        assert result.code == FetchResultCode.COOLDOWN
        fetcher.login.assert_not_awaited()
        assert "wait" in result.details
        assert "lastUpdate" in result.details
