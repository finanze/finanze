from datetime import date

import pytest

from domain.dezimal import Dezimal
from domain.exception.exceptions import MissingFieldsError
from domain.global_position import InstallmentFrequency, InterestType
from domain.loan_calculator import LoanCalculationParams
from infrastructure.loan_calculator import LoanCalculator


def _calculator() -> LoanCalculator:
    return LoanCalculator()


def _params(
    loan_amount=Dezimal(100000),
    interest_rate=Dezimal("0.03"),
    interest_type=InterestType.FIXED,
    euribor_rate=None,
    fixed_years=None,
    start=date(2020, 1, 15),
    end=date(2050, 1, 15),
    principal_outstanding=None,
    fixed_interest_rate=None,
    installment_frequency=InstallmentFrequency.MONTHLY,
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
        fixed_interest_rate=fixed_interest_rate,
        installment_frequency=installment_frequency,
    )


# ---------------------------------------------------------------------------
# TestValidation
# ---------------------------------------------------------------------------


class TestValidation:
    @pytest.mark.asyncio
    async def test_raises_when_both_amounts_missing(self):
        calc = _calculator()
        params = _params(loan_amount=None, principal_outstanding=None)

        with pytest.raises(MissingFieldsError) as exc_info:
            await calc.calculate(params)

        assert any(
            "loan_amount" in f and "principal_outstanding" in f
            for f in exc_info.value.missing_fields
        )

    @pytest.mark.asyncio
    async def test_raises_when_euribor_missing_for_variable(self):
        calc = _calculator()
        params = _params(interest_type=InterestType.VARIABLE, euribor_rate=None)

        with pytest.raises(MissingFieldsError) as exc_info:
            await calc.calculate(params)

        assert any("euribor_rate" in f for f in exc_info.value.missing_fields)

    @pytest.mark.asyncio
    async def test_raises_when_euribor_missing_for_mixed(self):
        calc = _calculator()
        params = _params(
            interest_type=InterestType.MIXED,
            euribor_rate=None,
            fixed_years=5,
        )

        with pytest.raises(MissingFieldsError) as exc_info:
            await calc.calculate(params)

        assert any("euribor_rate" in f for f in exc_info.value.missing_fields)

    @pytest.mark.asyncio
    async def test_raises_when_fixed_years_missing_for_mixed(self):
        calc = _calculator()
        params = _params(
            interest_type=InterestType.MIXED,
            euribor_rate=Dezimal("0.01"),
            fixed_years=None,
        )

        with pytest.raises(MissingFieldsError) as exc_info:
            await calc.calculate(params)

        assert any("fixed_years" in f for f in exc_info.value.missing_fields)

    @pytest.mark.asyncio
    async def test_accepts_valid_fixed_params(self):
        calc = _calculator()
        params = _params()

        result = await calc.calculate(params)

        assert result is not None
        assert result.current_installment_payment is not None


# ---------------------------------------------------------------------------
# TestFixedRate
# ---------------------------------------------------------------------------


class TestFixedRate:
    @pytest.mark.asyncio
    async def test_fixed_with_loan_amount(self):
        calc = _calculator()
        params = _params(
            loan_amount=Dezimal(200000),
            interest_rate=Dezimal("0.025"),
        )

        result = await calc.calculate(params)

        assert result.current_installment_payment is not None
        assert result.current_installment_payment.val > 0
        assert result.current_installment_interests is not None
        assert result.current_installment_interests.val > 0
        assert result.principal_outstanding is not None
        assert result.principal_outstanding.val > 0

    @pytest.mark.asyncio
    async def test_fixed_with_principal_outstanding_only(self):
        calc = _calculator()
        params = _params(
            loan_amount=None,
            principal_outstanding=Dezimal(80000),
            interest_rate=Dezimal("0.03"),
        )

        result = await calc.calculate(params)

        assert result.current_installment_payment is not None
        assert result.current_installment_payment.val > 0
        assert result.principal_outstanding == Dezimal(80000)

    @pytest.mark.asyncio
    async def test_fixed_zero_interest(self):
        calc = _calculator()
        params = _params(
            loan_amount=Dezimal(120000),
            interest_rate=Dezimal(0),
        )

        result = await calc.calculate(params)

        assert result.current_installment_interests == Dezimal(0)
        assert result.current_installment_payment is not None
        assert result.current_installment_payment.val > 0

    @pytest.mark.asyncio
    async def test_fixed_result_has_installment_date(self):
        calc = _calculator()
        params = _params()

        result = await calc.calculate(params)

        assert result.installment_date is not None
        assert isinstance(result.installment_date, date)


# ---------------------------------------------------------------------------
# TestVariableRate
# ---------------------------------------------------------------------------


class TestVariableRate:
    @pytest.mark.asyncio
    async def test_variable_with_loan_amount(self):
        calc = _calculator()
        params = _params(
            loan_amount=Dezimal(150000),
            interest_rate=Dezimal("0.01"),
            interest_type=InterestType.VARIABLE,
            euribor_rate=Dezimal("0.035"),
        )

        result = await calc.calculate(params)

        assert result.current_installment_payment is not None
        assert result.current_installment_payment.val > 0
        assert result.current_installment_interests is not None
        assert result.current_installment_interests.val > 0
        assert result.principal_outstanding is not None
        assert result.principal_outstanding.val > 0

    @pytest.mark.asyncio
    async def test_variable_with_principal_outstanding(self):
        calc = _calculator()
        params = _params(
            loan_amount=None,
            principal_outstanding=Dezimal(90000),
            interest_rate=Dezimal("0.015"),
            interest_type=InterestType.VARIABLE,
            euribor_rate=Dezimal("0.02"),
        )

        result = await calc.calculate(params)

        assert result.current_installment_payment is not None
        assert result.current_installment_payment.val > 0
        assert result.principal_outstanding == Dezimal(90000)

    @pytest.mark.asyncio
    async def test_variable_combined_rate_higher_payment(self):
        """A VARIABLE loan whose combined rate exceeds a FIXED rate
        should produce a higher monthly payment for the same principal."""
        calc = _calculator()

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

        fixed_result = await calc.calculate(fixed_params)
        variable_result = await calc.calculate(variable_params)

        assert (
            variable_result.current_installment_payment
            > fixed_result.current_installment_payment
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
        calc = _calculator()
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

        result = await calc.calculate(params)

        assert result.current_installment_payment is not None
        assert result.current_installment_payment.val > 0
        # During the fixed period, interest should be based on base rate only
        # interest_if_euribor_included would be outstanding * (base + euribor) / 12
        interest_with_euribor = outstanding * (base_rate + euribor) / Dezimal(12)
        assert result.current_installment_interests.val < interest_with_euribor.val

    @pytest.mark.asyncio
    async def test_mixed_with_principal_outstanding(self):
        calc = _calculator()
        params = _params(
            loan_amount=None,
            principal_outstanding=Dezimal(75000),
            interest_rate=Dezimal("0.025"),
            interest_type=InterestType.MIXED,
            euribor_rate=Dezimal("0.015"),
            fixed_years=5,
        )

        result = await calc.calculate(params)

        assert result.current_installment_payment is not None
        assert result.current_installment_payment.val > 0
        assert result.principal_outstanding == Dezimal(75000)


# ---------------------------------------------------------------------------
# TestInstallmentDate
# ---------------------------------------------------------------------------


class TestInstallmentDate:
    @pytest.mark.asyncio
    async def test_installment_date_in_future(self):
        """For a loan that started in the past, the next installment date
        should be on or after today."""
        calc = _calculator()
        params = _params(
            start=date(2020, 1, 15),
            end=date(2050, 1, 15),
        )

        result = await calc.calculate(params)

        today = date.today()
        assert result.installment_date is not None
        assert result.installment_date >= today


# ---------------------------------------------------------------------------
# TestFixedRateWithOutstandingOnly
# ---------------------------------------------------------------------------


class TestFixedRateWithOutstandingOnly:
    @pytest.mark.asyncio
    async def test_recovers_annuity_and_interests(self):
        calc = _calculator()
        params = _params(
            loan_amount=None,
            principal_outstanding=Dezimal(80000),
            interest_rate=Dezimal("0.03"),
        )

        result = await calc.calculate(params)

        assert result.current_installment_payment is not None
        assert result.current_installment_payment.val > 0
        assert result.current_installment_interests is not None
        assert result.current_installment_interests.val > 0
        assert result.principal_outstanding == Dezimal(80000)

    @pytest.mark.asyncio
    async def test_zero_interest_even_division(self):
        calc = _calculator()
        params = _params(
            loan_amount=None,
            principal_outstanding=Dezimal(60000),
            interest_rate=Dezimal(0),
        )

        result = await calc.calculate(params)

        assert result.current_installment_interests == Dezimal(0)
        assert result.current_installment_payment is not None
        assert result.current_installment_payment.val > 0


# ---------------------------------------------------------------------------
# TestMixedWithOutstandingOnly
# ---------------------------------------------------------------------------


class TestMixedWithOutstandingOnly:
    @pytest.mark.asyncio
    async def test_fixed_period_interests_exclude_euribor(self):
        calc = _calculator()
        base_rate = Dezimal("0.02")
        euribor = Dezimal("0.03")
        outstanding = Dezimal(75000)

        params = _params(
            loan_amount=None,
            principal_outstanding=outstanding,
            interest_rate=base_rate,
            interest_type=InterestType.MIXED,
            euribor_rate=euribor,
            fixed_years=50,
        )

        result = await calc.calculate(params)

        interest_with_euribor = outstanding * (base_rate + euribor) / Dezimal(12)
        assert result.current_installment_interests.val < interest_with_euribor.val

    @pytest.mark.asyncio
    async def test_variable_period_interests_include_euribor(self):
        calc = _calculator()
        base_rate = Dezimal("0.02")
        euribor = Dezimal("0.03")
        outstanding = Dezimal(75000)

        params = _params(
            loan_amount=None,
            principal_outstanding=outstanding,
            interest_rate=base_rate,
            interest_type=InterestType.MIXED,
            euribor_rate=euribor,
            fixed_years=1,
            start=date(2020, 1, 15),
            end=date(2050, 1, 15),
        )

        result = await calc.calculate(params)

        interest_fixed_only = outstanding * base_rate / Dezimal(12)
        assert result.current_installment_interests.val > interest_fixed_only.val


# ---------------------------------------------------------------------------
# TestInstallmentFrequencies
# ---------------------------------------------------------------------------


class TestInstallmentFrequencies:
    @pytest.mark.asyncio
    async def test_quarterly_higher_than_monthly(self):
        calc = _calculator()
        monthly = await calc.calculate(_params())
        quarterly = await calc.calculate(
            _params(installment_frequency=InstallmentFrequency.QUARTERLY)
        )
        assert (
            quarterly.current_installment_payment > monthly.current_installment_payment
        )

    @pytest.mark.asyncio
    async def test_semiannual_higher_than_quarterly(self):
        calc = _calculator()
        quarterly = await calc.calculate(
            _params(installment_frequency=InstallmentFrequency.QUARTERLY)
        )
        semiannual = await calc.calculate(
            _params(installment_frequency=InstallmentFrequency.SEMIANNUAL)
        )
        assert (
            semiannual.current_installment_payment
            > quarterly.current_installment_payment
        )

    @pytest.mark.asyncio
    async def test_yearly_highest(self):
        calc = _calculator()
        semiannual = await calc.calculate(
            _params(installment_frequency=InstallmentFrequency.SEMIANNUAL)
        )
        yearly = await calc.calculate(
            _params(installment_frequency=InstallmentFrequency.YEARLY)
        )
        assert (
            yearly.current_installment_payment > semiannual.current_installment_payment
        )

    @pytest.mark.asyncio
    async def test_biweekly_lower_than_monthly(self):
        calc = _calculator()
        monthly = await calc.calculate(_params())
        biweekly = await calc.calculate(
            _params(installment_frequency=InstallmentFrequency.BIWEEKLY)
        )
        assert (
            biweekly.current_installment_payment < monthly.current_installment_payment
        )

    @pytest.mark.asyncio
    async def test_weekly_lower_than_biweekly(self):
        calc = _calculator()
        biweekly = await calc.calculate(
            _params(installment_frequency=InstallmentFrequency.BIWEEKLY)
        )
        weekly = await calc.calculate(
            _params(installment_frequency=InstallmentFrequency.WEEKLY)
        )
        assert weekly.current_installment_payment < biweekly.current_installment_payment


# ---------------------------------------------------------------------------
# TestInterestBreakdown
# ---------------------------------------------------------------------------


class TestInterestBreakdown:
    @pytest.mark.asyncio
    async def test_interests_approximate_outstanding_times_period_rate(self):
        calc = _calculator()
        outstanding = Dezimal(100000)
        rate = Dezimal("0.036")

        params = _params(
            loan_amount=None,
            principal_outstanding=outstanding,
            interest_rate=rate,
        )

        result = await calc.calculate(params)

        expected = (outstanding * rate / Dezimal(12)).val.quantize(
            Dezimal("0.01").val, rounding="ROUND_HALF_UP"
        )
        assert result.current_installment_interests == Dezimal(expected)

    @pytest.mark.asyncio
    async def test_interests_decrease_with_lower_outstanding(self):
        calc = _calculator()
        rate = Dezimal("0.036")

        high = await calc.calculate(
            _params(
                loan_amount=None,
                principal_outstanding=Dezimal(100000),
                interest_rate=rate,
            )
        )
        low = await calc.calculate(
            _params(
                loan_amount=None,
                principal_outstanding=Dezimal(50000),
                interest_rate=rate,
            )
        )

        assert low.current_installment_interests < high.current_installment_interests
