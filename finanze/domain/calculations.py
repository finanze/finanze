from __future__ import annotations

from enum import Enum
from typing import List, Optional

from domain.dezimal import Dezimal
from pydantic.dataclasses import dataclass


class SavingsPeriodicity(str, Enum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"

    @property
    def periods_per_year(self) -> int:
        if self is SavingsPeriodicity.MONTHLY:
            return 12
        if self is SavingsPeriodicity.QUARTERLY:
            return 4
        return 1


@dataclass
class SavingsScenarioRequest:
    scenario_id: str
    annual_market_performance: Dezimal
    periodic_contribution: Optional[Dezimal] = None
    target_amount: Optional[Dezimal] = None


@dataclass
class SavingsRetirementRequest:
    withdrawal_amount: Optional[Dezimal] = None
    withdrawal_years: Optional[int] = None


@dataclass
class SavingsCalculationRequest:
    base_amount: Optional[Dezimal]
    years: Optional[int]
    periodicity: SavingsPeriodicity
    scenarios: List[SavingsScenarioRequest]
    retirement: Optional[SavingsRetirementRequest] = None


@dataclass
class SavingsPeriodEntry:
    period_index: int
    contributed: Dezimal
    total_contributed: Dezimal
    revaluation: Dezimal
    total_revaluation: Dezimal
    total_invested: Dezimal
    balance: Dezimal


@dataclass
class SavingsRetirementPeriodEntry:
    period_index: int
    withdrawal: Dezimal
    total_withdrawn: Dezimal
    revaluation: Dezimal
    balance: Dezimal


@dataclass
class SavingsScenarioResult:
    scenario_id: str
    annual_market_performance: Dezimal
    periodic_contribution: Dezimal
    accumulation_periods: List[SavingsPeriodEntry]
    total_contributions: Dezimal
    total_revaluation: Dezimal
    final_balance: Dezimal
    retirement: Optional[SavingsRetirementResult]


@dataclass
class SavingsRetirementResult:
    withdrawal_amount: Dezimal
    duration_periods: int
    duration_years: Dezimal
    total_withdrawn: Dezimal
    periods: List[SavingsRetirementPeriodEntry]


@dataclass
class SavingsCalculationResult:
    scenarios: List[SavingsScenarioResult]
