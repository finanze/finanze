from __future__ import annotations

from dataclasses import replace
from decimal import InvalidOperation, ROUND_HALF_UP
from typing import List, Optional

from domain.calculations import (
    SavingsCalculationRequest,
    SavingsCalculationResult,
    SavingsPeriodEntry,
    SavingsPeriodicity,
    SavingsRetirementPeriodEntry,
    SavingsRetirementRequest,
    SavingsRetirementResult,
    SavingsScenarioRequest,
    SavingsScenarioResult,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import CalculationInputError, MissingFieldsError
from domain.use_cases.calculate_savings import CalculateSavings


class CalculateSavingsImpl(CalculateSavings):
    async def execute(
        self, request: SavingsCalculationRequest
    ) -> SavingsCalculationResult:
        self._validate(request)
        data = replace(request)
        if data.base_amount is None:
            data.base_amount = Dezimal(0)
        scenarios = [self._normalize_scenario(s, data) for s in data.scenarios]
        if data.years and data.years > 0:
            total_periods = data.years * data.periodicity.periods_per_year
            return SavingsCalculationResult(
                scenarios=[
                    self._run_scenario(data, scenario, total_periods)
                    for scenario in scenarios
                ]
            )
        else:
            return SavingsCalculationResult(
                scenarios=[
                    self._run_scenario(
                        data,
                        scenario,
                        self._resolve_periods_for_scenario(data, scenario),
                    )
                    for scenario in scenarios
                ]
            )

    def _resolve_periods_for_scenario(
        self,
        request: SavingsCalculationRequest,
        scenario: SavingsScenarioRequest,
    ) -> int:
        if scenario.target_amount and request.base_amount:
            implied = self._solve_periods_for_target(request, scenario)
            if implied:
                return implied
        raise CalculationInputError(
            "years must be provided or derivable from scenario target and contribution"
        )

    def _solve_periods_for_target(
        self, request: SavingsCalculationRequest, scenario: SavingsScenarioRequest
    ) -> Optional[int]:
        if not scenario.target_amount or request.base_amount is None:
            return None
        rate = self._period_rate(
            scenario.annual_market_performance, request.periodicity
        )
        base = request.base_amount
        periodic = scenario.periodic_contribution or Dezimal(0)
        if rate == Dezimal(0) and periodic == Dezimal(0):
            return None
        periods = 0
        balance = base
        target = scenario.target_amount
        while balance < target and periods < 200 * request.periodicity.periods_per_year:
            balance = balance + periodic
            balance = balance + (balance * rate)
            periods += 1
        if balance < target:
            return None
        return periods if periods > 0 else None

    def _normalize_scenario(
        self, scenario: SavingsScenarioRequest, request: SavingsCalculationRequest
    ) -> SavingsScenarioRequest:
        normalized = replace(scenario)
        rate = self._period_rate(
            normalized.annual_market_performance, request.periodicity
        )
        if (
            normalized.target_amount is None
            and normalized.periodic_contribution is None
            and request.retirement
            and request.retirement.withdrawal_amount is not None
            and request.retirement.withdrawal_years is not None
        ):
            retirement_target = self._retirement_target_balance(
                rate, request.retirement, request.periodicity
            )
            if retirement_target is not None:
                normalized = replace(normalized, target_amount=retirement_target)
                normalized = replace(
                    normalized,
                    periodic_contribution=self._solve_contribution_for_retirement(
                        request, normalized, rate
                    ),
                )
        if normalized.periodic_contribution is None:
            if normalized.target_amount is None:
                normalized = replace(normalized, periodic_contribution=Dezimal(0))
            else:
                horizon_periods = None
                if request.years is not None and request.years > 0:
                    horizon_periods = (
                        request.years * request.periodicity.periods_per_year
                    )
                if horizon_periods is None or horizon_periods <= 0:
                    derived_periods = self._solve_periods_for_target(
                        request, normalized
                    )
                    horizon_periods = derived_periods
                if horizon_periods is None or horizon_periods <= 0:
                    raise CalculationInputError(
                        "years required to solve periodic contribution"
                    )
                normalized = replace(
                    normalized,
                    periodic_contribution=self._solve_required_contribution_periods(
                        request,
                        normalized,
                        horizon_periods,
                    ),
                )
        if normalized.target_amount is None:
            normalized = replace(normalized, target_amount=Dezimal(0))
        return normalized

    def _solve_contribution_for_retirement(
        self,
        request: SavingsCalculationRequest,
        scenario: SavingsScenarioRequest,
        rate: Dezimal,
    ) -> Dezimal:
        if (
            request.retirement is None
            or request.retirement.withdrawal_amount is None
            or request.retirement.withdrawal_years is None
            or request.years is None
            or request.years <= 0
        ):
            return Dezimal(0)
        retirement_periods = (
            request.retirement.withdrawal_years * request.periodicity.periods_per_year
        )
        accumulation_periods = request.years * request.periodicity.periods_per_year
        withdrawal = request.retirement.withdrawal_amount
        base = request.base_amount or Dezimal(0)
        initial_estimate = self._estimate_contribution_for_retirement(
            base, rate, accumulation_periods, withdrawal, retirement_periods
        )
        contribution = self._refine_contribution_via_simulation(
            base,
            rate,
            accumulation_periods,
            withdrawal,
            retirement_periods,
            initial_estimate,
        )
        return self._round_cents(contribution)

    def _estimate_contribution_for_retirement(
        self,
        base: Dezimal,
        rate: Dezimal,
        accumulation_periods: int,
        withdrawal: Dezimal,
        retirement_periods: int,
    ) -> Dezimal:
        if rate == Dezimal(0):
            total_needed = withdrawal * Dezimal(retirement_periods)
            if total_needed <= base:
                return Dezimal(0)
            shortfall = total_needed - base
            return shortfall / Dezimal(accumulation_periods)
        growth = (Dezimal(1) + rate) ** accumulation_periods
        base_at_retirement = base * growth
        discount = Dezimal(1) - (Dezimal(1) + rate) ** (-retirement_periods)
        pv_ordinary = withdrawal * discount / rate
        required_balance = pv_ordinary * (Dezimal(1) + rate)
        if required_balance <= base_at_retirement:
            return Dezimal(0)
        shortfall = required_balance - base_at_retirement
        annuity = (growth - Dezimal(1)) / rate
        return shortfall / annuity

    def _refine_contribution_via_simulation(
        self,
        base: Dezimal,
        rate: Dezimal,
        accumulation_periods: int,
        withdrawal: Dezimal,
        retirement_periods: int,
        initial_estimate: Dezimal,
    ) -> Dezimal:
        low = Dezimal(0)
        high = initial_estimate * Dezimal(3)
        if high == Dezimal(0):
            high = withdrawal * Dezimal(2)
        tolerance = Dezimal("0.01")
        for _ in range(100):
            mid = (low + high) / Dezimal(2)
            final_balance = self._simulate_full_cycle(
                base, rate, accumulation_periods, mid, withdrawal, retirement_periods
            )
            if abs(final_balance) < tolerance:
                return mid
            if final_balance > Dezimal(0):
                high = mid
            else:
                low = mid
        return (low + high) / Dezimal(2)

    def _simulate_full_cycle(
        self,
        base: Dezimal,
        rate: Dezimal,
        accumulation_periods: int,
        contribution: Dezimal,
        withdrawal: Dezimal,
        retirement_periods: int,
    ) -> Dezimal:
        balance = base
        for _ in range(accumulation_periods):
            balance = balance + contribution
            balance = balance + self._round_cents(balance * rate)
        final_balance = self._simulate_retirement_balance(
            balance, rate, retirement_periods, withdrawal
        )
        return final_balance

    def _solve_required_contribution_periods(
        self,
        request: SavingsCalculationRequest,
        scenario: SavingsScenarioRequest,
        periods: int,
    ) -> Dezimal:
        if scenario.target_amount is None:
            return Dezimal(0)
        if periods <= 0:
            return Dezimal(0)
        base = request.base_amount or Dezimal(0)
        target = scenario.target_amount
        rate = self._period_rate(
            scenario.annual_market_performance, request.periodicity
        )
        growth = (Dezimal(1) + rate) ** periods
        target_remaining = target - (base * growth)
        if target_remaining <= Dezimal(0):
            return Dezimal(0)
        if rate == Dezimal(0):
            return self._round_cents(target_remaining / Dezimal(periods))
        annuity_factor = ((Dezimal(1) + rate) ** periods - Dezimal(1)) / rate
        contribution = target_remaining / annuity_factor
        return self._round_cents(contribution)

    def _run_scenario(
        self,
        request: SavingsCalculationRequest,
        scenario: SavingsScenarioRequest,
        total_periods: int,
    ) -> SavingsScenarioResult:
        periods = total_periods
        rate = self._period_rate(
            scenario.annual_market_performance, request.periodicity
        )
        accumulation_periods: List[SavingsPeriodEntry] = []
        balance = request.base_amount or Dezimal(0)
        total_contrib = Dezimal(0)
        total_revaluation = Dezimal(0)
        base_amount = request.base_amount or Dezimal(0)
        for idx in range(1, periods + 1):
            contribution = scenario.periodic_contribution
            balance = balance + contribution
            total_contrib = total_contrib + contribution
            revaluation = self._round_cents(balance * rate)
            balance = balance + revaluation
            total_revaluation = total_revaluation + revaluation
            total_invested = self._round_cents(base_amount + total_contrib)
            accumulation_periods.append(
                SavingsPeriodEntry(
                    period_index=idx,
                    contributed=self._round_cents(contribution),
                    total_contributed=self._round_cents(total_contrib),
                    revaluation=self._round_cents(revaluation),
                    total_revaluation=self._round_cents(total_revaluation),
                    total_invested=total_invested,
                    balance=self._round_cents(balance),
                )
            )
        retirement_result = None
        if request.retirement:
            retirement_result = self._compute_retirement(
                request.retirement,
                balance,
                rate,
                request.periodicity,
            )
        return SavingsScenarioResult(
            scenario_id=scenario.scenario_id,
            annual_market_performance=scenario.annual_market_performance,
            periodic_contribution=self._round_cents(scenario.periodic_contribution),
            accumulation_periods=accumulation_periods,
            total_contributions=self._round_cents(total_contrib),
            total_revaluation=self._round_cents(total_revaluation),
            final_balance=self._round_cents(balance),
            retirement=retirement_result,
        )

    def _retirement_target_balance(
        self,
        rate: Dezimal,
        retirement: SavingsRetirementRequest,
        periodicity: SavingsPeriodicity,
    ) -> Optional[Dezimal]:
        if (
            retirement.withdrawal_amount is None
            or retirement.withdrawal_years is None
            or retirement.withdrawal_years <= 0
        ):
            return None
        periods = retirement.withdrawal_years * periodicity.periods_per_year
        if periods <= 0:
            return None
        amount = retirement.withdrawal_amount
        if rate == Dezimal(0):
            return self._round_cents(amount * Dezimal(periods))
        discount = Dezimal(1) - (Dezimal(1) + rate) ** (-periods)
        if discount == Dezimal(0):
            return self._round_cents(amount * Dezimal(periods))
        pv_ordinary = amount * discount / rate
        target = pv_ordinary * (Dezimal(1) + rate)
        return self._round_cents(target)

    def _compute_retirement(
        self,
        retirement: SavingsRetirementRequest,
        balance: Dezimal,
        rate: Dezimal,
        periodicity: SavingsPeriodicity,
    ) -> SavingsRetirementResult:
        periods_target = None
        if retirement.withdrawal_years is not None:
            periods_target = retirement.withdrawal_years * periodicity.periods_per_year
        if retirement.withdrawal_amount is not None:
            amount = retirement.withdrawal_amount
        elif periods_target is not None and periods_target > 0:
            amount = self._solve_withdrawal_amount(balance, rate, periods_target)
        else:
            amount = Dezimal(0)
        periods: List[SavingsRetirementPeriodEntry] = []
        current_balance = balance
        total_withdrawn = Dezimal(0)
        index = 1
        safety_limit = (
            periods_target
            if periods_target is not None
            else 100 * periodicity.periods_per_year
        )
        while current_balance > Dezimal(0):
            if safety_limit is not None and index > safety_limit:
                break
            withdrawal = amount if current_balance >= amount else current_balance
            current_balance = current_balance - withdrawal
            total_withdrawn = total_withdrawn + withdrawal
            revaluation = self._round_cents(current_balance * rate)
            current_balance = current_balance + revaluation
            periods.append(
                SavingsRetirementPeriodEntry(
                    period_index=index,
                    withdrawal=self._round_cents(withdrawal),
                    total_withdrawn=self._round_cents(total_withdrawn),
                    revaluation=self._round_cents(revaluation),
                    balance=self._round_cents(current_balance),
                )
            )
            index += 1
            if amount == Dezimal(0):
                break
        duration_periods = len(periods)
        duration_years = (
            Dezimal(duration_periods) / Dezimal(periodicity.periods_per_year)
            if duration_periods > 0
            else Dezimal(0)
        )
        return SavingsRetirementResult(
            withdrawal_amount=self._round_cents(amount),
            duration_periods=duration_periods,
            duration_years=self._round_cents(duration_years),
            total_withdrawn=self._round_cents(total_withdrawn),
            periods=periods,
        )

    def _simulate_retirement_balance(
        self,
        balance: Dezimal,
        rate: Dezimal,
        periods: int,
        withdrawal: Dezimal,
    ) -> Dezimal:
        current = balance
        for i in range(1, periods + 1):
            if current <= Dezimal(0):
                remaining_periods = periods - i + 1
                return Dezimal(0) - (withdrawal * Dezimal(remaining_periods))
            w = withdrawal if current >= withdrawal else current
            current = current - w
            if i < periods and current > Dezimal(0):
                current = current + self._round_cents(current * rate)
        return current

    def _solve_withdrawal_amount(
        self, balance: Dezimal, rate: Dezimal, periods_target: int
    ) -> Dezimal:
        if periods_target <= 0:
            return Dezimal(0)
        if rate == Dezimal(0):
            return self._round_cents(balance / Dezimal(periods_target))
        discount = Dezimal(1) - (Dezimal(1) + rate) ** (-periods_target)
        if discount == Dezimal(0):
            return self._round_cents(balance / Dezimal(periods_target))
        pv_factor = (discount / rate) * (Dezimal(1) + rate)
        withdrawal = balance / pv_factor
        return self._round_cents(withdrawal)

    def _period_rate(
        self, annual_rate: Dezimal, periodicity: SavingsPeriodicity
    ) -> Dezimal:
        periods = periodicity.periods_per_year
        if periods <= 0:
            return Dezimal(0)
        return annual_rate / periods

    def _round_cents(self, amount: Dezimal) -> Dezimal:
        if not amount.val.is_finite():
            raise CalculationInputError("calculation produced non-finite amount")
        try:
            return Dezimal(
                amount.val.quantize(Dezimal(0.01).val, rounding=ROUND_HALF_UP)
            )
        except InvalidOperation as error:
            raise CalculationInputError(
                "calculation produced non-finite amount"
            ) from error

    def _validate(self, request: SavingsCalculationRequest) -> None:
        missing: list[str] = []
        if request.base_amount is None:
            missing.append("base_amount")
        if request.years is not None and request.years <= 0:
            missing.append("years")
        if not request.scenarios:
            missing.append("scenarios")
        if missing:
            raise MissingFieldsError(missing)
        for scenario in request.scenarios:
            if scenario.annual_market_performance is None:
                raise MissingFieldsError(
                    [f"scenario:{scenario.scenario_id}:annual_market_performance"]
                )
        if request.retirement:
            r = request.retirement
            if r.withdrawal_amount is None and r.withdrawal_years is None:
                raise MissingFieldsError(
                    [
                        "retirement.withdrawal_amount | retirement.withdrawal_years",
                    ]
                )
