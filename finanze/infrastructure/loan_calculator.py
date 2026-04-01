from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import ROUND_HALF_UP

from application.ports.loan_calculator_port import LoanCalculatorPort
from dateutil.relativedelta import relativedelta
from domain.dezimal import Dezimal
from domain.exception.exceptions import MissingFieldsError
from domain.global_position import InstallmentFrequency, InterestType
from domain.loan_calculator import LoanCalculationParams, LoanCalculationResult


class LoanCalculator(LoanCalculatorPort):
    """
    Intelligent loan calculator that supports FIXED, VARIABLE, and MIXED interest types.

    - Rates are annual nominal (0.03 = 3% APR). Period rate = annual / payments_per_year.
    - For VARIABLE and MIXED after the fixed period, annual = interest_rate + euribor_rate.
    - For MIXED during the fixed period, annual = fixed_interest_rate (if provided) or interest_rate.
    - If principal_outstanding is not provided, it is computed by simulating amortization
      from the start date using the applicable rates over time.
    - Current installment payment is computed using remaining term and current annual rate.
    - Installment interests = current outstanding * current period rate.
    """

    async def calculate(self, params: LoanCalculationParams) -> LoanCalculationResult:
        today = date.today()

        self._validate(params)

        # Normalize params to avoid accidental mutation from callers
        p = replace(params)

        current_annual_rate = self._current_annual_rate(p, today)
        ppy = p.installment_frequency.payments_per_year
        period_rate = self._to_period_rate(current_annual_rate, ppy)

        next_inst_date = self._next_installment_date(p, today)

        # Fixed-rate optimization: compute payment from original schedule (constant A)
        if p.interest_type == InterestType.FIXED and p.loan_amount is not None:
            # Standard schedule: first payment at start + 1 period; last payment at 'end'.
            # Total installments N = periods between start and end.
            total_periods = max(
                1, self._full_months_between(p.start, p.end) * ppy // 12
            )
            # Payments made before next_inst_date
            payments_made = max(
                0, self._full_months_between(p.start, next_inst_date) * ppy // 12 - 1
            )

            A = self._amortizing_payment(p.loan_amount, period_rate, total_periods)
            outstanding = p.principal_outstanding or self._remaining_balance(
                p.loan_amount, period_rate, total_periods, payments_made, A
            )

            interest_part = self._round_cents(outstanding * period_rate)
            return LoanCalculationResult(
                current_installment_payment=self._round_cents(A),
                current_installment_interests=interest_part,
                principal_outstanding=self._round_cents(outstanding),
                installment_date=next_inst_date,
            )

        # FIXED-rate with provided outstanding but no loan_amount: recover original A from RB_k
        if (
            p.interest_type == InterestType.FIXED
            and p.loan_amount is None
            and p.principal_outstanding is not None
        ):
            N = max(1, self._full_months_between(p.start, p.end) * ppy // 12)
            k = max(
                0, self._full_months_between(p.start, next_inst_date) * ppy // 12 - 1
            )
            r = period_rate
            RBk = p.principal_outstanding

            if r == Dezimal(0):
                # No interest: A is simply original principal / N; with only RBk we can't recover P reliably.
                # Fall back to dividing RBk evenly over remaining periods.
                remaining_periods = max(
                    1, self._full_months_between(next_inst_date, p.end) * ppy // 12
                )
                period_payment = self._round_cents(RBk / remaining_periods)
                return LoanCalculationResult(
                    current_installment_payment=period_payment,
                    current_installment_interests=Dezimal(0),
                    principal_outstanding=RBk,
                    installment_date=next_inst_date,
                )

            D = Dezimal(1) - (Dezimal(1) + r) ** (-N)
            factor = (Dezimal(1) + r) ** k
            coeff = factor - (factor - Dezimal(1)) / D

            if coeff.val == 0:
                # Fallback to general formula using remaining periods
                remaining_periods = max(
                    1, self._full_months_between(next_inst_date, p.end) * ppy // 12
                )
                denom = Dezimal(1) - (Dezimal(1) + r) ** (-remaining_periods)
                period_payment = RBk if denom.val == 0 else RBk * r / denom
                return LoanCalculationResult(
                    current_installment_payment=self._round_cents(period_payment),
                    current_installment_interests=self._round_cents(RBk * r),
                    principal_outstanding=RBk,
                    installment_date=next_inst_date,
                )

            P0 = RBk / coeff
            A = P0 * r / D
            return LoanCalculationResult(
                current_installment_payment=self._round_cents(A),
                current_installment_interests=self._round_cents(RBk * r),
                principal_outstanding=RBk,
                installment_date=next_inst_date,
            )

        # General path (VARIABLE or MIXED or when loan_amount is missing):
        # Determine outstanding and remaining periods
        outstanding = p.principal_outstanding
        if outstanding is None:
            outstanding = self._compute_outstanding_from_start(p, today)

        # Remaining installments from next_inst_date to end.
        # If we are given principal_outstanding (calculating from now), consider end as exclusive.
        # If we are calculating from a computed outstanding (from start), include the end installment.
        if p.principal_outstanding is not None:
            # For FIXED, treat end as exclusive (previous logic).
            # For VARIABLE/MIXED, treat end as inclusive (add +1 to months before conversion).
            if p.interest_type in (InterestType.VARIABLE, InterestType.MIXED):
                remaining_periods = max(
                    1,
                    (self._full_months_between(next_inst_date, p.end) + 1) * ppy // 12,
                )
            else:
                remaining_periods = max(
                    1, self._full_months_between(next_inst_date, p.end) * ppy // 12
                )
        else:
            remaining_periods = max(
                1, (self._full_months_between(next_inst_date, p.end) + 1) * ppy // 12
            )

        # If there is only interest (edge case), handle gracefully
        if period_rate == Dezimal(0):
            # Purely principal division over remaining periods
            period_payment = self._round_cents(outstanding / remaining_periods)
            interest_part = Dezimal(0)
            return LoanCalculationResult(
                current_installment_payment=period_payment,
                current_installment_interests=interest_part,
                principal_outstanding=outstanding,
                installment_date=next_inst_date,
            )

        # Standard amortizing payment formula: A = P * r / (1 - (1+r)^-n)
        r = period_rate
        P = outstanding
        n = remaining_periods
        denom = Dezimal(1) - (Dezimal(1) + r) ** (-n)
        if denom.val == 0:
            period_payment = P
        else:
            period_payment = P * r / denom

        # Round to cents (2 decimals) using bank-style rounding
        period_payment = self._round_cents(period_payment)

        interest_part = self._round_cents(outstanding * period_rate)

        return LoanCalculationResult(
            current_installment_payment=period_payment,
            current_installment_interests=interest_part,
            principal_outstanding=outstanding,
            installment_date=next_inst_date,
        )

    def _validate(self, params: LoanCalculationParams) -> None:
        missing: list[str] = []
        if params.loan_amount is None and params.principal_outstanding is None:
            missing.append("loan_amount | principal_outstanding (at least one)")
        if params.start is None:
            missing.append("start")
        if params.end is None:
            missing.append("end")
        if params.interest_rate is None:
            missing.append("interest_rate")
        if params.interest_type in (InterestType.VARIABLE, InterestType.MIXED):
            if params.euribor_rate is None:
                missing.append("euribor_rate (required for VARIABLE/MIXED)")
        if params.interest_type is InterestType.MIXED and not params.fixed_years:
            missing.append("fixed_years (required for MIXED)")
        if missing:
            raise MissingFieldsError(missing)

    def _current_annual_rate(self, p: LoanCalculationParams, today: date) -> Dezimal:
        base = p.interest_rate
        if p.interest_type == InterestType.FIXED:
            return base
        if p.interest_type == InterestType.VARIABLE:
            return base + p.euribor_rate
        # MIXED
        assert p.fixed_years is not None
        fixed_end = p.start + relativedelta(years=p.fixed_years)
        if today < fixed_end:
            return p.fixed_interest_rate if p.fixed_interest_rate is not None else base
        return base + p.euribor_rate

    def _to_period_rate(self, annual: Dezimal, payments_per_year: int) -> Dezimal:
        return annual / payments_per_year

    def _months_between(self, d1: date, d2: date) -> int:
        if d2 <= d1:
            return 0
        rd = relativedelta(d2, d1)
        return rd.years * 12 + rd.months + (1 if rd.days > 0 else 0)

    def _full_months_between(self, d1: date, d2: date) -> int:
        if d2 <= d1:
            return 0
        rd = relativedelta(d2, d1)
        return rd.years * 12 + rd.months

    def _period_step(self, freq: InstallmentFrequency) -> relativedelta:
        """Return the relativedelta step corresponding to one payment period."""
        mapping = {
            InstallmentFrequency.WEEKLY: relativedelta(weeks=1),
            InstallmentFrequency.BIWEEKLY: relativedelta(weeks=2),
            InstallmentFrequency.SEMIMONTHLY: relativedelta(days=15),
            InstallmentFrequency.MONTHLY: relativedelta(months=1),
            InstallmentFrequency.BIMONTHLY: relativedelta(months=2),
            InstallmentFrequency.QUARTERLY: relativedelta(months=3),
            InstallmentFrequency.SEMIANNUAL: relativedelta(months=6),
            InstallmentFrequency.YEARLY: relativedelta(years=1),
        }
        return mapping.get(freq, relativedelta(months=1))

    def _compute_outstanding_from_start(
        self, p: LoanCalculationParams, today: date
    ) -> Dezimal:
        assert p.loan_amount is not None
        principal = p.loan_amount

        if today <= p.start:
            return principal

        ppy = p.installment_frequency.payments_per_year
        step = self._period_step(p.installment_frequency)

        # Simulate period-by-period amortization from start up to last payment before today.
        outstanding = principal
        current_date = p.start

        while current_date < today and current_date < p.end:
            annual_rate = self._annual_rate_at(p, current_date)
            period_rate = self._to_period_rate(annual_rate, ppy)

            # Remaining periods counting from the next due date
            remaining_months = max(1, self._full_months_between(current_date, p.end))
            remaining_periods = max(1, remaining_months * ppy // 12)

            # Payment for this period under current regime
            if period_rate == Dezimal(0):
                payment = self._round_cents(outstanding / remaining_periods)
                interest = Dezimal(0)
            else:
                denom = Dezimal(1) - (Dezimal(1) + period_rate) ** (-remaining_periods)
                payment = self._round_cents(outstanding * period_rate / denom)
                interest = self._round_cents(outstanding * period_rate)

            principal_paid = payment - interest
            outstanding = max(Dezimal(0), outstanding - principal_paid)

            # step forward by one period
            current_date = current_date + step

            if outstanding == Dezimal(0):
                break

        return outstanding

    def _annual_rate_at(self, p: LoanCalculationParams, when: date) -> Dezimal:
        base = p.interest_rate
        if p.interest_type == InterestType.FIXED:
            return base
        if p.interest_type == InterestType.VARIABLE:
            return base + p.euribor_rate  # type: ignore[arg-type]
        # MIXED
        assert p.fixed_years is not None
        fixed_end = p.start + relativedelta(years=p.fixed_years)
        if when < fixed_end:
            return p.fixed_interest_rate if p.fixed_interest_rate is not None else base
        return base + p.euribor_rate  # type: ignore[arg-type]

    # Finance helpers
    def _amortizing_payment(self, P: Dezimal, r: Dezimal, n: int) -> Dezimal:
        if n <= 0:
            return P
        if r == Dezimal(0):
            return P / n
        denom = Dezimal(1) - (Dezimal(1) + r) ** (-n)
        return P * r / denom

    def _remaining_balance(
        self, P: Dezimal, r: Dezimal, n: int, k: int, A: Dezimal | None = None
    ) -> Dezimal:
        """Remaining balance after k payments on an amortizing loan.
        If A not provided, compute it from P, r, n.
        Formula: RB_k = P*(1+r)^k - A * ((1+r)^k - 1)/r
        """
        if k <= 0:
            return P
        if k >= n:
            return Dezimal(0)
        if r == Dezimal(0):
            A = A or (P / n)
            return max(Dezimal(0), P - A * k)
        A = A or self._amortizing_payment(P, r, n)
        factor = (Dezimal(1) + r) ** k
        return max(Dezimal(0), P * factor - A * ((factor - Dezimal(1)) / r))

    def _round_cents(self, value: Dezimal) -> Dezimal:
        # Use Decimal quantize via underlying decimal to 2 places, ROUND_HALF_UP
        q = value.val.quantize(Dezimal(0.01).val, rounding=ROUND_HALF_UP)
        return Dezimal(q)

    def _next_installment_date(self, p: LoanCalculationParams, today: date) -> date:
        """Return the next installment date on or after today, capped by end date.
        Installments are aligned to the start date with the configured frequency.
        """
        # If today is before or equal to start, next is start
        if today <= p.start:
            return p.start

        # Walk periods until we reach >= today (limit to end date)
        step = self._period_step(p.installment_frequency)
        candidate = p.start
        while candidate < today and candidate < p.end:
            candidate = candidate + step

        return min(candidate, p.end)
