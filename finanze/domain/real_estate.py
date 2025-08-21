from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.earnings_expenses import PeriodicFlow
from domain.file_upload import FileUpload
from domain.global_position import InterestType, LoanType
from pydantic.dataclasses import dataclass


class RealEstateFlowSubtype(str, Enum):
    LOAN = "LOAN"
    SUPPLY = "SUPPLY"
    COST = "COST"
    RENT = "RENT"


@dataclass
class LoanPayload:
    type: LoanType
    loan_amount: Optional[Dezimal]
    interest_rate: Dezimal
    euribor_rate: Optional[Dezimal]
    interest_type: InterestType
    fixed_years: Optional[int]
    principal_outstanding: Dezimal
    monthly_interests: Optional[Dezimal] = None


@dataclass
class RentPayload:
    pass


@dataclass
class SupplyPayload:
    tax_deductible: bool = False


@dataclass
class CostPayload:
    tax_deductible: bool = False


RealEstateFlowPayload = LoanPayload | RentPayload | SupplyPayload | CostPayload


@dataclass
class RealEstateFlow:
    periodic_flow_id: Optional[UUID]
    periodic_flow: Optional[PeriodicFlow]
    flow_subtype: RealEstateFlowSubtype
    description: str
    payload: RealEstateFlowPayload


@dataclass
class PurchaseExpense:
    concept: str
    amount: Dezimal
    description: Optional[str]


@dataclass
class Valuation:
    date: date
    amount: Dezimal
    notes: Optional[str]


@dataclass
class Location:
    address: Optional[str] = None
    cadastral_reference: Optional[str] = None


@dataclass
class BasicInfo:
    name: str
    is_residence: bool
    is_rented: bool
    bathrooms: Optional[int] = None
    bedrooms: Optional[int] = None
    photo_url: Optional[str] = None


@dataclass
class PurchaseInfo:
    date: date
    price: Dezimal
    expenses: List[PurchaseExpense]


@dataclass
class ValuationInfo:
    estimated_market_value: Dezimal
    valuations: List[Valuation]
    annual_appreciation: Optional[Dezimal] = None


@dataclass
class Amortization:
    concept: str
    base_amount: Dezimal
    amount: Dezimal
    percentage: Dezimal


@dataclass
class RentalData:
    amortizations: List[Amortization]
    marginal_tax_rate: Optional[Dezimal] = None
    vacancy_rate: Optional[Dezimal] = None


@dataclass
class RealEstate:
    id: Optional[UUID]
    basic_info: BasicInfo
    location: Location
    purchase_info: PurchaseInfo
    valuation_info: ValuationInfo
    flows: List[RealEstateFlow]
    currency: str
    rental_data: Optional[RentalData]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CreateRealEstateRequest:
    real_estate: RealEstate
    photo: Optional[FileUpload]


@dataclass
class UpdateRealEstateRequest:
    real_estate: RealEstate
    remove_unassigned_flows: bool
    photo: Optional[FileUpload]


@dataclass
class DeleteRealEstateRequest:
    id: Optional[UUID]
    remove_related_flows: bool
