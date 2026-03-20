from datetime import date

import pytest

from application.use_cases.calculate_loan import CalculateLoanImpl
from domain.dezimal import Dezimal
from domain.exception.exceptions import MissingFieldsError
from domain.global_position import InterestType
from domain.loan_calculator import LoanCalculationParams


def _use_case() -> CalculateLoanImpl:
    return CalculateLoanImpl()


def _params(
    loan_amount=Dezimal(100000),
    interest_rate=Dezimal("0.03"),
    interest_type=InterestType.FIXED,
    euribor_rate=None,
    fixed_years=None,
    start=date(2020, 1, 15),
    end=date(2050, 1, 15),
    principal_outstanding=None,
) -> LoanCalculationParams:
    return LoanCalculationParams(
        loan_amount=loan_amount,
        interest_rate=interest_rate,
        interest_type=interest_type,
        euribor_rate=euribor_rate,
        fixed_years=fixed_years,
        start=start,
        end=end,
        principal_outstanding=principal_outstanding,
    )


# ---------------------------------------------------------------------------
# TestValidation
# ---------------------------------------------------------------------------


class TestValidation:
    @pytest.mark.asyncio
    async def test_raises_when_both_amounts_missing(self):
        uc = _use_case()
        params = _params(loan_amount=None, principal_outstanding=None)

        with pytest.raises(MissingFieldsError) as exc_info:
            await uc.execute(params)

        assert any(
            "loan_amount" in f and "principal_outstanding" in f
            for f in exc_info.value.missing_fields
        )

    @pytest.mark.asyncio
    async def test_raises_when_euribor_missing_for_variable(self):
        uc = _use_case()
        params = _params(interest_type=InterestType.VARIABLE, euribor_rate=None)

        with pytest.raises(MissingFieldsError) as exc_info:
            await uc.execute(params)

        assert any("euribor_rate" in f for f in exc_info.value.missing_fields)

    @pytest.mark.asyncio
    async def test_raises_when_euribor_missing_for_mixed(self):
        uc = _use_case()
        params = _params(
            interest_type=InterestType.MIXED,
            euribor_rate=None,
            fixed_years=5,
        )

        with pytest.raises(MissingFieldsError) as exc_info:
            await uc.execute(params)

        assert any("euribor_rate" in f for f in exc_info.value.missing_fields)

    @pytest.mark.asyncio
    async def test_raises_when_fixed_years_missing_for_mixed(self):
        uc = _use_case()
        params = _params(
            interest_type=InterestType.MIXED,
            euribor_rate=Dezimal("0.01"),
            fixed_years=None,
        )

        with pytest.raises(MissingFieldsError) as exc_info:
            await uc.execute(params)

        assert any("fixed_years" in f for f in exc_info.value.missing_fields)

    @pytest.mark.asyncio
    async def test_accepts_valid_fixed_params(self):
        uc = _use_case()
        params = _params()

        result = await uc.execute(params)

        assert result is not None
        assert result.current_monthly_payment is not None


# ---------------------------------------------------------------------------
# TestFixedRate
# ---------------------------------------------------------------------------


class TestFixedRate:
    @pytest.mark.asyncio
    async def test_fixed_with_loan_amount(self):
        uc = _use_case()
        params = _params(
            loan_amount=Dezimal(200000),
            interest_rate=Dezimal("0.025"),
        )

        result = await uc.execute(params)

        assert result.current_monthly_payment is not None
        assert result.current_monthly_payment.val > 0
        assert result.current_monthly_interests is not None
        assert result.current_monthly_interests.val > 0
        assert result.principal_outstanding is not None
        assert result.principal_outstanding.val > 0

    @pytest.mark.asyncio
    async def test_fixed_with_principal_outstanding_only(self):
        uc = _use_case()
        params = _params(
            loan_amount=None,
            principal_outstanding=Dezimal(80000),
            interest_rate=Dezimal("0.03"),
        )

        result = await uc.execute(params)

        assert result.current_monthly_payment is not None
        assert result.current_monthly_payment.val > 0
        assert result.principal_outstanding == Dezimal(80000)

    @pytest.mark.asyncio
    async def test_fixed_zero_interest(self):
        uc = _use_case()
        params = _params(
            loan_amount=Dezimal(120000),
            interest_rate=Dezimal(0),
        )

        result = await uc.execute(params)

        assert result.current_monthly_interests == Dezimal(0)
        assert result.current_monthly_payment is not None
        assert result.current_monthly_payment.val > 0

    @pytest.mark.asyncio
    async def test_fixed_result_has_installment_date(self):
        uc = _use_case()
        params = _params()

        result = await uc.execute(params)

        assert result.installment_date is not None
        assert isinstance(result.installment_date, date)


# ---------------------------------------------------------------------------
# TestVariableRate
# ---------------------------------------------------------------------------


class TestVariableRate:
    @pytest.mark.asyncio
    async def test_variable_with_loan_amount(self):
        uc = _use_case()
        params = _params(
            loan_amount=Dezimal(150000),
            interest_rate=Dezimal("0.01"),
            interest_type=InterestType.VARIABLE,
            euribor_rate=Dezimal("0.035"),
        )

        result = await uc.execute(params)

        assert result.current_monthly_payment is not None
        assert result.current_monthly_payment.val > 0
        assert result.current_monthly_interests is not None
        assert result.current_monthly_interests.val > 0
        assert result.principal_outstanding is not None
        assert result.principal_outstanding.val > 0

    @pytest.mark.asyncio
    async def test_variable_with_principal_outstanding(self):
        uc = _use_case()
        params = _params(
            loan_amount=None,
            principal_outstanding=Dezimal(90000),
            interest_rate=Dezimal("0.015"),
            interest_type=InterestType.VARIABLE,
            euribor_rate=Dezimal("0.02"),
        )

        result = await uc.execute(params)

        assert result.current_monthly_payment is not None
        assert result.current_monthly_payment.val > 0
        assert result.principal_outstanding == Dezimal(90000)

    @pytest.mark.asyncio
    async def test_variable_combined_rate_higher_payment(self):
        """A VARIABLE loan whose combined rate exceeds a FIXED rate
        should produce a higher monthly payment for the same principal."""
        uc = _use_case()

        fixed_params = _params(
            loan_amount=None,
            principal_outstanding=Dezimal(100000),
            interest_rate=Dezimal("0.02"),
            interest_type=InterestType.FIXED,
        )

        variable_params = _params(
            loan_amount=None,
            principal_outstanding=Dezimal(100000),
            interest_rate=Dezimal("0.02"),
            interest_type=InterestType.VARIABLE,
            euribor_rate=Dezimal("0.03"),
        )

        fixed_result = await uc.execute(fixed_params)
        variable_result = await uc.execute(variable_params)

        assert (
            variable_result.current_monthly_payment
            > fixed_result.current_monthly_payment
        )


# ---------------------------------------------------------------------------
# TestMixedRate
# ---------------------------------------------------------------------------


class TestMixedRate:
    @pytest.mark.asyncio
    async def test_mixed_during_fixed_period(self):
        """When today is within the fixed period of a MIXED loan,
        the effective rate should equal the base rate (no euribor).
        We verify this by checking the interest component reflects only the
        base rate, not base + euribor."""
        uc = _use_case()
        base_rate = Dezimal("0.02")
        euribor = Dezimal("0.03")
        outstanding = Dezimal(80000)

        params = _params(
            loan_amount=None,
            principal_outstanding=outstanding,
            interest_rate=base_rate,
            interest_type=InterestType.MIXED,
            euribor_rate=euribor,
            fixed_years=50,
            start=date(2020, 1, 15),
            end=date(2050, 1, 15),
        )

        result = await uc.execute(params)

        assert result.current_monthly_payment is not None
        assert result.current_monthly_payment.val > 0
        # During the fixed period, interest should be based on base rate only
        # interest_if_euribor_included would be outstanding * (base + euribor) / 12
        interest_with_euribor = outstanding * (base_rate + euribor) / Dezimal(12)
        assert result.current_monthly_interests.val < interest_with_euribor.val

    @pytest.mark.asyncio
    async def test_mixed_with_principal_outstanding(self):
        uc = _use_case()
        params = _params(
            loan_amount=None,
            principal_outstanding=Dezimal(75000),
            interest_rate=Dezimal("0.025"),
            interest_type=InterestType.MIXED,
            euribor_rate=Dezimal("0.015"),
            fixed_years=5,
        )

        result = await uc.execute(params)

        assert result.current_monthly_payment is not None
        assert result.current_monthly_payment.val > 0
        assert result.principal_outstanding == Dezimal(75000)


# ---------------------------------------------------------------------------
# TestInstallmentDate
# ---------------------------------------------------------------------------


class TestInstallmentDate:
    @pytest.mark.asyncio
    async def test_installment_date_in_future(self):
        """For a loan that started in the past, the next installment date
        should be on or after today."""
        uc = _use_case()
        params = _params(
            start=date(2020, 1, 15),
            end=date(2050, 1, 15),
        )

        result = await uc.execute(params)

        today = date.today()
        assert result.installment_date is not None
        assert result.installment_date >= today
