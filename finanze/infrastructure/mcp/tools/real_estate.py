from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.exception.exceptions import RealEstateNotFound
from domain.real_estate import (
    BasicInfo,
    CreateRealEstateRequest,
    DeleteRealEstateRequest,
    Location,
    PurchaseInfo,
    RealEstate,
    RentalData,
    UpdateRealEstateRequest,
    ValuationInfo,
)
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.use_cases import McpUseCases


class BasicInfoInput(BaseModel):
    name: str = Field(min_length=1)
    is_residence: bool = Field(
        default=False, description="Whether it is the user's habitual residence."
    )
    is_rented: bool = False
    bathrooms: Optional[int] = Field(default=None, ge=0)
    bedrooms: Optional[int] = Field(default=None, ge=0)


class LocationInput(BaseModel):
    address: Optional[str] = None
    cadastral_reference: Optional[str] = None


class PurchaseExpenseInput(BaseModel):
    concept: str = Field(min_length=1, description="e.g. taxes, notary, agency.")
    amount: Decimal = Field(ge=0)
    description: Optional[str] = None


class PurchaseInfoInput(BaseModel):
    date: date
    price: Decimal = Field(ge=0)
    expenses: list[PurchaseExpenseInput] = Field(default_factory=list)


class ValuationInput(BaseModel):
    date: date
    amount: Decimal = Field(ge=0)
    notes: Optional[str] = None
    market_value: bool = Field(
        default=False,
        description="Whether it is a market value appraisal, used as the current value.",
    )


class ValuationInfoInput(BaseModel):
    valuations: list[ValuationInput] = Field(
        min_length=1,
        description="Valuation history. At least one with market_value=true, the latest of them is the current value.",
    )
    annual_appreciation: Optional[Decimal] = Field(
        default=None, description="Expected yearly appreciation, e.g. 0.03 for 3%."
    )


class AmortizationInput(BaseModel):
    concept: str = Field(min_length=1)
    base_amount: Decimal
    amount: Decimal
    percentage: Decimal


class RentalDataInput(BaseModel):
    marginal_tax_rate: Optional[Decimal] = Field(
        default=None, description="e.g. 0.3 for 30%."
    )
    vacancy_rate: Optional[Decimal] = Field(
        default=None, description="e.g. 0.05 for 5%."
    )
    amortizations: list[AmortizationInput] = Field(default_factory=list)


def _section(model: Optional[BaseModel], cls):
    return cls(**model.model_dump()) if model is not None else None


def _valuation_info(model: Optional[ValuationInfoInput]) -> Optional[ValuationInfo]:
    if model is None:
        return None
    return ValuationInfo(estimated_market_value=Dezimal(0), **model.model_dump())


def register(registry: ToolRegistry, ucs: McpUseCases):
    @registry.read("List real estate")
    async def list_real_estate():
        """List the user's real estate properties with purchase info, valuations, rental data and linked flows (rent, loans, costs, supplies)."""
        return await ucs.list_real_estate.execute()

    @registry.write("Save real estate")
    async def save_real_estate(
        real_estate_id: Annotated[
            Optional[UUID],
            Field(description="Existing property ID to update. Omit to create one."),
        ] = None,
        basic_info: Optional[BasicInfoInput] = None,
        location: Optional[LocationInput] = None,
        purchase_info: Optional[PurchaseInfoInput] = None,
        valuation_info: Optional[ValuationInfoInput] = None,
        currency: Annotated[
            Optional[str],
            Field(
                min_length=3,
                max_length=3,
                description="Property currency. Only on create, it cannot be changed.",
            ),
        ] = None,
        rental_data: Optional[RentalDataInput] = None,
    ):
        """Create a real estate property, or update one by real_estate_id. On update only the provided sections are replaced. On create basic_info, purchase_info, valuation_info and currency are required. Linked flows (rent, mortgage, costs) and photos are managed in the Finanze app and kept on update."""
        if real_estate_id:
            current = next(
                (
                    r
                    for r in await ucs.list_real_estate.execute()
                    if r.id == real_estate_id
                ),
                None,
            )
            if current is None:
                raise RealEstateNotFound(real_estate_id)
            changes = {
                "basic_info": _section(basic_info, BasicInfo),
                "location": _section(location, Location),
                "purchase_info": _section(purchase_info, PurchaseInfo),
                "valuation_info": _valuation_info(valuation_info),
                "rental_data": _section(rental_data, RentalData),
            }
            updated = replace(
                current, **{k: v for k, v in changes.items() if v is not None}
            )
            await ucs.update_real_estate.execute(
                UpdateRealEstateRequest(
                    real_estate=updated, remove_unassigned_flows=False, photo=None
                )
            )
            return {"updated": str(real_estate_id)}

        missing = [
            name
            for name, value in {
                "basic_info": basic_info,
                "purchase_info": purchase_info,
                "valuation_info": valuation_info,
                "currency": currency,
            }.items()
            if value is None
        ]
        if missing:
            raise ToolError(f"Missing required fields: {', '.join(missing)}")
        real_estate = RealEstate(
            id=None,
            basic_info=_section(basic_info, BasicInfo),
            location=_section(location, Location) or Location(),
            purchase_info=_section(purchase_info, PurchaseInfo),
            valuation_info=_valuation_info(valuation_info),
            flows=[],
            currency=currency.upper(),
            rental_data=_section(rental_data, RentalData),
        )
        await ucs.create_real_estate.execute(
            CreateRealEstateRequest(real_estate=real_estate, photo=None)
        )
        return {"created": str(real_estate.id)}

    @registry.write("Delete real estate", destructive=True, idempotent=True)
    async def delete_real_estate(
        real_estate_id: Annotated[UUID, Field(description="Property ID.")],
        remove_related_flows: Annotated[
            bool,
            Field(description="Also delete its linked periodic flows."),
        ] = False,
    ):
        """Delete a real estate property."""
        await ucs.delete_real_estate.execute(
            DeleteRealEstateRequest(
                id=real_estate_id, remove_related_flows=remove_related_flows
            )
        )
        return {"deleted": str(real_estate_id)}
