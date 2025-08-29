from domain.real_estate import (
    CostPayload,
    LoanPayload,
    RealEstate,
    RentPayload,
    SupplyPayload,
)
from domain.use_cases.list_real_estate import ListRealEstate
from flask import jsonify


def _serialize_flow_payload(payload) -> dict:
    """Serialize the payload based on its type."""
    if isinstance(payload, LoanPayload):
        return {
            "type": payload.type,
            "loan_amount": payload.loan_amount,
            "interest_rate": payload.interest_rate,
            "euribor_rate": payload.euribor_rate,
            "interest_type": payload.interest_type,
            "fixed_years": payload.fixed_years,
            "principal_outstanding": payload.principal_outstanding,
            "monthly_interests": payload.monthly_interests,
        }
    elif isinstance(payload, CostPayload) or isinstance(payload, SupplyPayload):
        return {
            "tax_deductible": payload.tax_deductible,
        }
    elif isinstance(payload, RentPayload):
        return {}
    else:
        return {}


def _serialize_real_estate(real_estate: RealEstate) -> dict:
    return {
        "id": str(real_estate.id),
        "basic_info": {
            "name": real_estate.basic_info.name,
            "photo_url": real_estate.basic_info.photo_url,
            "is_residence": real_estate.basic_info.is_residence,
            "is_rented": real_estate.basic_info.is_rented,
            "bathrooms": real_estate.basic_info.bathrooms,
            "bedrooms": real_estate.basic_info.bedrooms,
        },
        "location": {
            "address": real_estate.location.address,
            "cadastral_reference": real_estate.location.cadastral_reference,
        },
        "purchase_info": {
            "date": real_estate.purchase_info.date.isoformat(),
            "price": real_estate.purchase_info.price,
            "expenses": [
                {
                    "concept": expense.concept,
                    "amount": expense.amount,
                    "description": expense.description,
                }
                for expense in real_estate.purchase_info.expenses
            ],
        },
        "valuation_info": {
            "estimated_market_value": real_estate.valuation_info.estimated_market_value,
            "annual_appreciation": real_estate.valuation_info.annual_appreciation,
            "valuations": [
                {
                    "date": valuation.date.isoformat(),
                    "amount": valuation.amount,
                    "notes": valuation.notes,
                }
                for valuation in real_estate.valuation_info.valuations
            ],
        },
        "flows": [
            {
                "periodic_flow_id": str(flow.periodic_flow_id),
                "flow_subtype": flow.flow_subtype,
                "description": flow.description,
                "payload": _serialize_flow_payload(flow.payload),
                "periodic_flow": {
                    "id": str(flow.periodic_flow.id),
                    "name": flow.periodic_flow.name,
                    "amount": flow.periodic_flow.amount,
                    "currency": flow.periodic_flow.currency,
                    "flow_type": flow.periodic_flow.flow_type,
                    "frequency": flow.periodic_flow.frequency,
                    "category": flow.periodic_flow.category,
                    "enabled": flow.periodic_flow.enabled,
                    "since": flow.periodic_flow.since.isoformat()
                    if flow.periodic_flow.since
                    else None,
                    "until": flow.periodic_flow.until.isoformat()
                    if flow.periodic_flow.until
                    else None,
                    "icon": flow.periodic_flow.icon,
                    "next_date": flow.periodic_flow.next_date.isoformat()
                    if flow.periodic_flow.next_date
                    else None,
                    "max_amount": flow.periodic_flow.max_amount,
                }
                if flow.periodic_flow
                else None,
            }
            for flow in real_estate.flows
        ],
        "currency": real_estate.currency,
        "created_at": real_estate.created_at.isoformat(),
        "updated_at": real_estate.updated_at.isoformat()
        if real_estate.updated_at
        else None,
        "rental_data": (
            {
                "marginal_tax_rate": real_estate.rental_data.marginal_tax_rate,
                "vacancy_rate": real_estate.rental_data.vacancy_rate,
                "amortizations": [
                    {
                        "concept": a.concept,
                        "base_amount": a.base_amount,
                        "amount": a.amount,
                        "percentage": a.percentage,
                    }
                    for a in real_estate.rental_data.amortizations
                ],
            }
            if real_estate.rental_data is not None
            else None
        ),
    }


def list_real_estate(list_real_estate_uc: ListRealEstate):
    real_estates = list_real_estate_uc.execute()
    return jsonify([_serialize_real_estate(re) for re in real_estates]), 200
