from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import ROUND_HALF_UP

from dateutil.relativedelta import relativedelta
from domain.dezimal import Dezimal
from domain.exception.exceptions import MissingFieldsError
from domain.global_position import InterestType
from domain.loan_calculator import LoanCalculationParams, LoanCalculationResult
from domain.use_cases.calculate_loan import CalculateLoan


class CalculateLoanImpl(CalculateLoan):
    """
    Intelligent loan calculator that supports FIXED, VARIABLE, and MIXED interest types.

    - Rates are annual nominal (0.03 = 3% APR). Monthly rate = annual / 12.
    - For VARIABLE and MIXED after the fixed period, annual = interest_rate + euribor_rate.
    - If principal_outstanding is not provided, it is computed by simulating amortization
      from the start date using the applicable rates over time.
    - Current monthly installment is computed using remaining term and current annual rate.
    - Monthly interests = current outstanding * current monthly rate.
    """

    async def execute(self, params: LoanCalculationParams) -> LoanCalculationResult:
        today = date.today()

        self._validate(params)

        # Normalize params to avoid accidental mutation from callers
        p = replace(params)

        current_annual_rate = self._current_annual_rate(p, today)
        monthly_rate = self._to_monthly_rate(current_annual_rate)

        next_inst_date = self._next_installment_date(p, today)

        # Fixed-rate optimization: compute payment from original schedule (constant A)
        if p.interest_type == InterestType.FIXED and p.loan_amount is not None:
            # Standard schedule: first payment at start + 1 month; last payment at 'end'.
            # Total installments N = months_between(start, end) (full months).
            total_months = max(1, self._full_months_between(p.start, p.end))
            # Payments made before next_inst_date: if next is at start + m, then made = m-1.
            payments_made = max(
                0, self._full_months_between(p.start, next_inst_date) - 1
            )

            A = self._amortizing_payment(p.loan_amount, monthly_rate, total_months)
            outstanding = p.principal_outstanding or self._remaining_balance(
                p.loan_amount, monthly_rate, total_months, payments_made, A
            )

            interest_part = self._round_cents(outstanding * monthly_rate)
            return LoanCalculationResult(
                current_monthly_payment=self._round_cents(A),
                current_monthly_interests=interest_part,
                principal_outstanding=self._round_cents(outstanding),
                installment_date=next_inst_date,
            )

        # FIXED-rate with provided outstanding but no loan_amount: recover original A from RB_k
        if (
            p.interest_type == InterestType.FIXED
            and p.loan_amount is None
            and p.principal_outstanding is not None
        ):
            N = max(1, self._full_months_between(p.start, p.end))
            k = max(0, self._full_months_between(p.start, next_inst_date) - 1)
            r = monthly_rate
            RBk = p.principal_outstanding

            if r == Dezimal(0):
                # No interest: A is simply original principal / N; with only RBk we can't recover P reliably.
                # Fall back to dividing RBk evenly over remaining installments.
                remaining_months = max(
                    1, self._full_months_between(next_inst_date, p.end)
                )
                monthly_payment = self._round_cents(RBk / remaining_months)
                return LoanCalculationResult(
                    current_monthly_payment=monthly_payment,
                    current_monthly_interests=Dezimal(0),
                    principal_outstanding=RBk,
                    installment_date=next_inst_date,
                )

            D = Dezimal(1) - (Dezimal(1) + r) ** (-N)
            factor = (Dezimal(1) + r) ** k
            coeff = factor - (factor - Dezimal(1)) / D

            if coeff.val == 0:
                # Fallback to general formula using remaining months
                remaining_months = max(
                    1, self._full_months_between(next_inst_date, p.end)
                )
                denom = Dezimal(1) - (Dezimal(1) + r) ** (-remaining_months)
                monthly_payment = RBk if denom.val == 0 else RBk * r / denom
                return LoanCalculationResult(
                    current_monthly_payment=self._round_cents(monthly_payment),
                    current_monthly_interests=self._round_cents(RBk * r),
                    principal_outstanding=RBk,
                    installment_date=next_inst_date,
                )

            P0 = RBk / coeff
            A = P0 * r / D
            return LoanCalculationResult(
                current_monthly_payment=self._round_cents(A),
                current_monthly_interests=self._round_cents(RBk * r),
                principal_outstanding=RBk,
                installment_date=next_inst_date,
            )

        # General path (VARIABLE or MIXED or when loan_amount is missing):
        # Determine outstanding and remaining months
        outstanding = p.principal_outstanding
        if outstanding is None:
            outstanding = self._compute_outstanding_from_start(p, today)

        # Remaining installments from next_inst_date to end.
        # If we are given principal_outstanding (calculating from now), consider end as exclusive.
        # If we are calculating from a computed outstanding (from start), include the end installment.
        if p.principal_outstanding is not None:
            # For FIXED, treat end as exclusive (previous logic).
            # For VARIABLE/MIXED, treat end as inclusive (add +1 to months).
            if p.interest_type in (InterestType.VARIABLE, InterestType.MIXED):
                remaining_months = max(
                    1, self._full_months_between(next_inst_date, p.end) + 1
                )
            else:
                remaining_months = max(
                    1, self._full_months_between(next_inst_date, p.end)
                )
        else:
            remaining_months = max(
                1, self._full_months_between(next_inst_date, p.end) + 1
            )

        # If there is only interest (edge case), handle gracefully
        if monthly_rate == Dezimal(0):
            # Purely principal division over remaining months
            monthly_payment = self._round_cents(outstanding / remaining_months)
            interest_part = Dezimal(0)
            return LoanCalculationResult(
                current_monthly_payment=monthly_payment,
                current_monthly_interests=interest_part,
                principal_outstanding=outstanding,
                installment_date=next_inst_date,
            )

        # Standard amortizing payment formula: A = P * r / (1 - (1+r)^-n)
        r = monthly_rate
        P = outstanding
        n = remaining_months
        denom = Dezimal(1) - (Dezimal(1) + r) ** (-n)
        if denom.val == 0:
            monthly_payment = P
        else:
            monthly_payment = P * r / denom

        # Round to cents (2 decimals) using bank-style rounding
        monthly_payment = self._round_cents(monthly_payment)

        interest_part = self._round_cents(outstanding * monthly_rate)

        return LoanCalculationResult(
            current_monthly_payment=monthly_payment,
            current_monthly_interests=interest_part,
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
            return base
        return base + p.euribor_rate

    def _to_monthly_rate(self, annual: Dezimal) -> Dezimal:
        return annual / 12

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

    def _compute_outstanding_from_start(
        self, p: LoanCalculationParams, today: date
    ) -> Dezimal:
        assert p.loan_amount is not None
        principal = p.loan_amount

        if today <= p.start:
            return principal

        # We'll simulate month-by-month amortization from start up to last payment before today.
        months_elapsed = self._months_between(p.start, today)
        if months_elapsed == 0:
            return principal

        # Compute dynamic payments per period depending on rate regime (for simplicity,
        # recompute payment whenever the annual rate regime changes, e.g., when MIXED crosses fixed boundary).
        current_date = p.start
        outstanding = principal
        # total_months not needed explicitly; we compute months_left each loop

        for m in range(months_elapsed):
            annual_rate = self._annual_rate_at(p, current_date)
            monthly_rate = self._to_monthly_rate(annual_rate)

            # Remaining installments counting from the next due date at (current_date + 1 month)
            months_left = max(1, self._full_months_between(current_date, p.end))

            # Payment for this month under current regime
            if monthly_rate == Dezimal(0):
                payment = self._round_cents(outstanding / months_left)
                interest = Dezimal(0)
            else:
                denom = Dezimal(1) - (Dezimal(1) + monthly_rate) ** (-months_left)
                payment = self._round_cents(outstanding * monthly_rate / denom)
                interest = self._round_cents(outstanding * monthly_rate)

            principal_paid = payment - interest
            outstanding = max(Dezimal(0), outstanding - principal_paid)

            # step 1 month forward
            current_date = current_date + relativedelta(months=1)

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
            return base
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
        """Assume monthly installments aligned to the day-of-month of the start date.
        Return the next installment date on or after today, capped by end date.
        """
        # If today is before or equal to start, next is start
        if today <= p.start:
            return p.start

        # Walk months until we reach >= today (limit to end date)
        # Align on start day-of-month when possible; relativedelta handles month rollovers
        candidate = p.start
        while candidate < today and candidate < p.end:
            candidate = candidate + relativedelta(months=1)

        return min(candidate, p.end)
