from datetime import date, datetime
from uuid import uuid4

from application.use_cases.forecast import ForecastImpl
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import (
    GlobalPosition,
    InterestType,
    Loan,
    Loans,
    LoanType,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
)


def _entity():
    return Entity(
        id=uuid4(),
        name="TestEntity",
        natural_id="test",
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _gp_with_recf(entries: list[RealEstateCFDetail]) -> GlobalPosition:
    return GlobalPosition(
        id=uuid4(),
        entity=_entity(),
        products={ProductType.REAL_ESTATE_CF: RealEstateCFInvestments(entries=entries)},
    )


def _recf(
    maturity: date,
    amount: Dezimal = Dezimal(1000),
    interest_rate: Dezimal = Dezimal("0.10"),
    extended_maturity: date | None = None,
    extended_interest_rate: Dezimal | None = None,
) -> RealEstateCFDetail:
    return RealEstateCFDetail(
        id=uuid4(),
        name="Project",
        amount=amount,
        pending_amount=amount,
        currency="EUR",
        interest_rate=interest_rate,
        start=datetime(2024, 1, 1),
        maturity=maturity,
        type="EQUITY",
        state="ACTIVE",
        extended_maturity=extended_maturity,
        extended_interest_rate=extended_interest_rate,
        source=DataSource.REAL,
    )


def _forecast_impl() -> ForecastImpl:
    return ForecastImpl(
        position_port=None,
        auto_contributions_port=None,
        periodic_flow_port=None,
        pending_flow_port=None,
        real_estate_port=None,
        entity_port=None,
    )


class TestLiquidateRecf:
    def test_no_extended_maturity_liquidated_when_past(self):
        entry = _recf(maturity=date(2026, 3, 1))
        gp = _gp_with_recf([entry])
        cash_delta = {}

        _forecast_impl()._liquidate_recf(gp, date(2026, 4, 10), cash_delta)

        assert len(gp.products[ProductType.REAL_ESTATE_CF].entries) == 0
        assert "EUR" in cash_delta

    def test_no_extended_maturity_kept_when_future(self):
        entry = _recf(maturity=date(2026, 6, 1))
        gp = _gp_with_recf([entry])
        cash_delta = {}

        _forecast_impl()._liquidate_recf(gp, date(2026, 4, 10), cash_delta)

        assert len(gp.products[ProductType.REAL_ESTATE_CF].entries) == 1
        assert cash_delta == {}

    def test_extended_maturity_future_keeps_entry(self):
        entry = _recf(
            maturity=date(2026, 5, 15),
            extended_maturity=date(2026, 8, 15),
        )
        gp = _gp_with_recf([entry])
        cash_delta = {}

        _forecast_impl()._liquidate_recf(gp, date(2026, 7, 1), cash_delta)

        assert len(gp.products[ProductType.REAL_ESTATE_CF].entries) == 1
        assert cash_delta == {}

    def test_extended_maturity_also_past_liquidates(self):
        entry = _recf(
            maturity=date(2026, 5, 15),
            extended_maturity=date(2026, 8, 15),
        )
        gp = _gp_with_recf([entry])
        cash_delta = {}

        _forecast_impl()._liquidate_recf(gp, date(2026, 9, 1), cash_delta)

        assert len(gp.products[ProductType.REAL_ESTATE_CF].entries) == 0
        assert "EUR" in cash_delta

    def test_extended_maturity_before_original_ignored(self):
        entry = _recf(
            maturity=date(2026, 8, 15),
            extended_maturity=date(2026, 5, 1),
        )
        gp = _gp_with_recf([entry])
        cash_delta = {}

        _forecast_impl()._liquidate_recf(gp, date(2026, 7, 1), cash_delta)

        assert len(gp.products[ProductType.REAL_ESTATE_CF].entries) == 1
        assert cash_delta == {}

    def test_mixed_entries_partial_liquidation(self):
        kept = _recf(
            maturity=date(2026, 5, 15),
            extended_maturity=date(2026, 8, 15),
        )
        liquidated = _recf(maturity=date(2026, 3, 1))
        gp = _gp_with_recf([kept, liquidated])
        cash_delta = {}

        _forecast_impl()._liquidate_recf(gp, date(2026, 6, 1), cash_delta)

        assert len(gp.products[ProductType.REAL_ESTATE_CF].entries) == 1
        assert gp.products[ProductType.REAL_ESTATE_CF].entries[0] is kept
        assert "EUR" in cash_delta


def _loan(
    *,
    outstanding: Dezimal = Dezimal(1200),
    loan_amount: Dezimal = Dezimal(2000),
    installment: Dezimal = Dezimal(100),
    interest_rate: Dezimal = Dezimal(0),
    interest_type: InterestType = InterestType.FIXED,
    creation: date = date(2020, 1, 1),
    loan_hash: str = "",
) -> Loan:
    return Loan(
        id=uuid4(),
        type=LoanType.STANDARD,
        currency="EUR",
        current_installment=installment,
        interest_rate=interest_rate,
        loan_amount=loan_amount,
        creation=creation,
        maturity=date(2035, 1, 1),
        principal_outstanding=outstanding,
        interest_type=interest_type,
        hash=loan_hash,
        source=DataSource.REAL,
    )


def _gp_with_loans(loans: list[Loan]) -> GlobalPosition:
    return GlobalPosition(
        id=uuid4(),
        entity=_entity(),
        products={ProductType.LOAN: Loans(entries=loans)},
    )


class TestAmortizeStandaloneLoans:
    def test_zero_interest_loan_amortized(self):
        loan = _loan(loan_hash="abc")
        gp = _gp_with_loans([loan])
        positions = {"e1": gp}

        _forecast_impl()._amortize_standalone_loans(
            positions, set(), date(2024, 7, 1), date(2024, 1, 1)
        )

        # 6 months * 100, no interest -> 1200 - 600 = 600
        assert loan.principal_outstanding == Dezimal(600)
        assert loan.principal_paid == Dezimal(1400)

    def test_linked_loan_skipped(self):
        loan = _loan(loan_hash="linked-hash")
        gp = _gp_with_loans([loan])
        positions = {"e1": gp}

        _forecast_impl()._amortize_standalone_loans(
            positions, {"linked-hash"}, date(2024, 7, 1), date(2024, 1, 1)
        )

        assert loan.principal_outstanding == Dezimal(1200)

    def test_past_target_leaves_loan_unchanged(self):
        loan = _loan(loan_hash="abc")
        gp = _gp_with_loans([loan])
        positions = {"e1": gp}

        _forecast_impl()._amortize_standalone_loans(
            positions, set(), date(2024, 1, 1), date(2024, 1, 1)
        )

        assert loan.principal_outstanding == Dezimal(1200)

    def test_outstanding_capped_at_zero(self):
        loan = _loan(outstanding=Dezimal(150), loan_amount=Dezimal(2000))
        gp = _gp_with_loans([loan])
        positions = {"e1": gp}

        _forecast_impl()._amortize_standalone_loans(
            positions, set(), date(2025, 1, 1), date(2024, 1, 1)
        )

        assert loan.principal_outstanding == Dezimal(0)
        assert loan.principal_paid == Dezimal(2000)

    def test_unhashed_loan_amortized(self):
        loan = _loan(loan_hash="")
        gp = _gp_with_loans([loan])
        positions = {str(gp.entity.id): gp}

        _forecast_impl()._amortize_standalone_loans(
            positions, set(), date(2024, 7, 1), date(2024, 1, 1)
        )

        assert loan.principal_outstanding == Dezimal(600)
