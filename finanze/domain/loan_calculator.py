from dataclasses import dataclass
from datetime import date
from typing import Optional

from domain.dezimal import Dezimal
from domain.global_position import InstallmentFrequency, InterestType


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
    fixed_interest_rate: Optional[Dezimal] = None
    installment_frequency: InstallmentFrequency = InstallmentFrequency.MONTHLY


@dataclass
class LoanCalculationResult:
    current_installment_payment: Optional[Dezimal]
    current_installment_interests: Optional[Dezimal]
    principal_outstanding: Optional[Dezimal]
    installment_date: Optional[date] = None
