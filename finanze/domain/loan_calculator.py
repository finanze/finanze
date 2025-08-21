from dataclasses import dataclass
from datetime import date
from typing import Optional

from domain.dezimal import Dezimal
from domain.global_position import InterestType


@dataclass
class LoanCalculationParams:
    loan_amount: Optional[Dezimal]
    interest_rate: Dezimal
    interest_type: InterestType
    euribor_rate: Optional[Dezimal]
    fixed_years: Optional[int]
    start: date
    end: date
    principal_outstanding: Optional[Dezimal]


@dataclass
class LoanCalculationResult:
    current_monthly_payment: Optional[Dezimal]
    current_monthly_interests: Optional[Dezimal]
    principal_outstanding: Optional[Dezimal]
    installment_date: Optional[date] = None
