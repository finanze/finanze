from datetime import date
from uuid import UUID

from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.global_position import InterestType, LoanType
from domain.real_estate import (
    BasicInfo,
    CostPayload,
    LoanPayload,
    Location,
    PurchaseExpense,
    PurchaseInfo,
    RealEstate,
    RealEstateFlow,
    RealEstateFlowSubtype,
    RentPayload,
    SupplyPayload,
    Valuation,
    ValuationInfo,
    RentalData,
    Amortization,
)


def map_real_estate(body: dict, real_estate_id: UUID = None) -> RealEstate:
    basic_info = BasicInfo(
        name=body["basic_info"]["name"],
        is_residence=body["basic_info"].get("is_residence", False),
        is_rented=body["basic_info"].get("is_rented", False),
        bathrooms=body["basic_info"].get("bathrooms"),
        bedrooms=body["basic_info"].get("bedrooms"),
    )

    # Parse location
    location = Location(
        address=body["location"].get("address"),
        cadastral_reference=body["location"].get("cadastral_reference"),
    )

    # Parse purchase info
    purchase_date = body["purchase_info"]["date"]
    if isinstance(purchase_date, str):
        purchase_date = date.fromisoformat(purchase_date)

    purchase_expenses = []
    for expense_data in body["purchase_info"].get("expenses", []):
        purchase_expenses.append(
            PurchaseExpense(
                concept=expense_data["concept"],
                amount=Dezimal(expense_data["amount"]),
                description=expense_data.get("description"),
            )
        )

    purchase_info = PurchaseInfo(
        date=purchase_date,
        price=Dezimal(body["purchase_info"]["price"]),
        expenses=purchase_expenses,
    )

    # Parse valuation info
    valuations = []
    for val_data in body["valuation_info"].get("valuations", []):
        val_date = val_data["date"]
        if isinstance(val_date, str):
            val_date = date.fromisoformat(val_date)

        valuations.append(
            Valuation(
                date=val_date,
                amount=Dezimal(val_data["amount"]),
                notes=val_data.get("notes"),
            )
        )

    annual_appreciation = body["valuation_info"].get("annual_appreciation")
    valuation_info = ValuationInfo(
        estimated_market_value=Dezimal(
            body["valuation_info"]["estimated_market_value"]
        ),
        valuations=valuations,
        annual_appreciation=Dezimal(annual_appreciation)
        if annual_appreciation is not None
        else None,
    )

    # Parse flows
    flows = []
    for flow_data in body.get("flows", []):
        flow_subtype = RealEstateFlowSubtype(flow_data["flow_subtype"])
        payload = _parse_flow_payload(flow_subtype, flow_data["payload"])

        periodic_flow_data = flow_data.get("periodic_flow", {})
        periodic_flow = None
        if periodic_flow_data:
            since_date = periodic_flow_data["since"]
            if isinstance(since_date, str):
                since_date = date.fromisoformat(since_date)

            until_date = periodic_flow_data.get("until") or None
            if until_date and isinstance(until_date, str):
                until_date = date.fromisoformat(until_date)

            periodic_flow = PeriodicFlow(
                id=UUID(periodic_flow_data["id"])
                if periodic_flow_data.get("id")
                else None,
                name=periodic_flow_data["name"],
                amount=Dezimal(periodic_flow_data["amount"]),
                currency=periodic_flow_data["currency"],
                flow_type=FlowType(periodic_flow_data["flow_type"]),
                frequency=FlowFrequency(periodic_flow_data["frequency"]),
                category=periodic_flow_data.get("category"),
                enabled=periodic_flow_data.get("enabled", True),
                since=since_date,
                until=until_date,
                icon=periodic_flow_data.get("icon"),
                max_amount=Dezimal(periodic_flow_data["max_amount"])
                if periodic_flow_data.get("max_amount")
                else None,
            )

        periodic_flow_id = flow_data.get("periodic_flow_id")
        if (
            (periodic_flow_id and periodic_flow_data) or periodic_flow_data
        ) and periodic_flow_id != periodic_flow_data.get("id"):
            raise ValueError("periodic_flow.id and periodic_flow_id not matching")

        flows.append(
            RealEstateFlow(
                periodic_flow_id=UUID(periodic_flow_id) if periodic_flow_id else None,
                periodic_flow=periodic_flow,
                flow_subtype=flow_subtype,
                description=flow_data["description"],
                payload=payload,
            )
        )

    # Parse rental data
    rental_data_obj = None
    rental_data = body.get("rental_data")
    if rental_data is not None:
        amortizations = None
        if isinstance(rental_data.get("amortizations"), list):
            amortizations = [
                Amortization(
                    concept=a["concept"],
                    base_amount=Dezimal(a["base_amount"]),
                    amount=Dezimal(a["amount"]),
                    percentage=Dezimal(a["percentage"]),
                )
                for a in rental_data.get("amortizations", [])
            ]
        mtr = rental_data.get("marginal_tax_rate")
        vr = rental_data.get("vacancy_rate")
        rental_data_obj = RentalData(
            amortizations=amortizations,
            marginal_tax_rate=Dezimal(mtr) if mtr is not None else None,
            vacancy_rate=Dezimal(vr) if vr is not None else None,
        )

    # Create real estate entity
    return RealEstate(
        id=real_estate_id,
        basic_info=basic_info,
        location=location,
        purchase_info=purchase_info,
        valuation_info=valuation_info,
        flows=flows,
        currency=body["currency"],
        rental_data=rental_data_obj,
    )


def _parse_flow_payload(flow_subtype: RealEstateFlowSubtype, payload_data: dict):
    if flow_subtype == RealEstateFlowSubtype.LOAN:
        return LoanPayload(
            type=LoanType(payload_data["type"]),
            loan_amount=Dezimal(payload_data["loan_amount"])
            if payload_data.get("loan_amount")
            else None,
            interest_rate=Dezimal(payload_data["interest_rate"]),
            euribor_rate=Dezimal(payload_data["euribor_rate"])
            if payload_data.get("euribor_rate")
            else None,
            interest_type=InterestType(payload_data["interest_type"]),
            fixed_years=payload_data.get("fixed_years"),
            principal_outstanding=Dezimal(payload_data["principal_outstanding"]),
            monthly_interests=Dezimal(payload_data["monthly_interests"])
            if payload_data.get("monthly_interests")
            else None,
        )
    elif flow_subtype == RealEstateFlowSubtype.RENT:
        return RentPayload()
    elif flow_subtype == RealEstateFlowSubtype.SUPPLY:
        return SupplyPayload(tax_deductible=payload_data.get("tax_deductible", False))
    elif flow_subtype == RealEstateFlowSubtype.COST:
        return CostPayload(tax_deductible=payload_data.get("tax_deductible", False))
    else:
        raise ValueError(f"Unknown flow type: {flow_subtype}")
