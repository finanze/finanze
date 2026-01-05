import json
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from application.ports.real_estate_port import RealEstatePort
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.global_position import InterestType, LoanType
from domain.real_estate import (
    Amortization,
    BasicInfo,
    CostPayload,
    LoanPayload,
    Location,
    PurchaseExpense,
    PurchaseInfo,
    RealEstate,
    RealEstateFlow,
    RealEstateFlowSubtype,
    RentalData,
    RentPayload,
    SupplyPayload,
    Valuation,
    ValuationInfo,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.real_estate.queries import RealEstateQueries


def _serialize_purchase_expense(expense: PurchaseExpense) -> dict:
    return {
        "concept": expense.concept,
        "amount": str(expense.amount),
        "description": expense.description,
    }


def _deserialize_purchase_expense(data: dict) -> PurchaseExpense:
    return PurchaseExpense(
        concept=data["concept"],
        amount=Dezimal(data["amount"]),
        description=data.get("description"),
    )


def _serialize_valuation(valuation: Valuation) -> dict:
    return {
        "date": valuation.date.isoformat(),
        "amount": str(valuation.amount),
        "notes": valuation.notes,
    }


def _deserialize_valuation(data: dict) -> Valuation:
    return Valuation(
        date=data["date"],
        amount=Dezimal(data["amount"]),
        notes=data.get("notes"),
    )


def _serialize_payload(payload) -> dict:
    if isinstance(payload, LoanPayload):
        return {
            "type": payload.type,
            "loan_amount": str(payload.loan_amount) if payload.loan_amount else None,
            "interest_rate": str(payload.interest_rate),
            "euribor_rate": str(payload.euribor_rate) if payload.euribor_rate else None,
            "interest_type": payload.interest_type,
            "fixed_years": payload.fixed_years,
            "principal_outstanding": str(payload.principal_outstanding),
            "monthly_interests": str(payload.monthly_interests)
            if payload.monthly_interests
            else None,
        }
    elif isinstance(payload, (CostPayload, SupplyPayload)):
        return {
            "tax_deductible": payload.tax_deductible,
        }
    elif isinstance(payload, RentPayload):
        return {}
    else:
        return {}


def _deserialize_payload(flow_subtype: RealEstateFlowSubtype, data: dict):
    if flow_subtype == RealEstateFlowSubtype.LOAN:
        return LoanPayload(
            type=LoanType(data["type"]),
            loan_amount=Dezimal(data["loan_amount"])
            if data.get("loan_amount")
            else None,
            interest_rate=Dezimal(data["interest_rate"]),
            euribor_rate=Dezimal(data["euribor_rate"])
            if data.get("euribor_rate")
            else None,
            interest_type=InterestType(data["interest_type"]),
            fixed_years=data.get("fixed_years"),
            principal_outstanding=Dezimal(data["principal_outstanding"]),
            monthly_interests=Dezimal(data["monthly_interests"])
            if data.get("monthly_interests")
            else None,
        )
    elif flow_subtype == RealEstateFlowSubtype.RENT:
        return RentPayload()
    elif flow_subtype == RealEstateFlowSubtype.SUPPLY:
        return SupplyPayload(tax_deductible=data.get("tax_deductible", False))
    elif flow_subtype == RealEstateFlowSubtype.COST:
        return CostPayload(tax_deductible=data.get("tax_deductible", False))


def _serialize_rental_data(rental_data: Optional[RentalData]) -> Optional[dict]:
    if rental_data is None:
        return None
    amortizations = [
        {
            "concept": a.concept,
            "base_amount": str(a.base_amount),
            "amount": str(a.amount),
            "percentage": str(a.percentage),
        }
        for a in rental_data.amortizations
    ]
    return {
        "marginal_tax_rate": str(rental_data.marginal_tax_rate)
        if rental_data.marginal_tax_rate is not None
        else None,
        "vacancy_rate": str(rental_data.vacancy_rate)
        if rental_data.vacancy_rate is not None
        else None,
        "amortizations": amortizations,
    }


def _deserialize_rental_data(data: Optional[str | bytes]) -> Optional[RentalData]:
    if not data:
        return None
    try:
        parsed = json.loads(data)
    except (TypeError, json.JSONDecodeError):
        return None
    amortizations_list = parsed.get("amortizations")
    amortizations = None
    if isinstance(amortizations_list, list):
        amortizations = [
            Amortization(
                concept=a.get("concept"),
                base_amount=Dezimal(a.get("base_amount"))
                if a.get("base_amount") is not None
                else Dezimal("0"),
                amount=Dezimal(a.get("amount"))
                if a.get("amount") is not None
                else Dezimal("0"),
                percentage=Dezimal(a.get("percentage"))
                if a.get("percentage") is not None
                else Dezimal("0"),
            )
            for a in amortizations_list
        ]
    mtr = parsed.get("marginal_tax_rate")
    vr = parsed.get("vacancy_rate")
    return RentalData(
        amortizations=amortizations,
        marginal_tax_rate=Dezimal(mtr) if mtr is not None else None,
        vacancy_rate=Dezimal(vr) if vr is not None else None,
    )


async def _build_flow(flow_row) -> RealEstateFlow:
    payload_data = json.loads(flow_row["payload"])
    payload = _deserialize_payload(
        RealEstateFlowSubtype(flow_row["flow_subtype"]), payload_data
    )

    return RealEstateFlow(
        periodic_flow_id=UUID(flow_row["periodic_flow_id"]),
        periodic_flow=PeriodicFlow(
            id=UUID(flow_row["periodic_flow_id"]),
            name=flow_row["name"],
            amount=Dezimal(flow_row["amount"]),
            currency=flow_row["currency"],
            flow_type=FlowType(flow_row["flow_type"]),
            frequency=FlowFrequency(flow_row["frequency"]),
            category=flow_row["category"],
            enabled=flow_row["enabled"],
            since=flow_row["since"],
            until=flow_row["until"],
            icon=flow_row["icon"],
            max_amount=Dezimal(flow_row["max_amount"])
            if flow_row["max_amount"]
            else None,
        ),
        flow_subtype=RealEstateFlowSubtype(flow_row["flow_subtype"]),
        description=flow_row["description"],
        payload=payload,
    )


async def _build_real_estate(row, cursor) -> RealEstate:
    await cursor.execute(
        RealEstateQueries.SELECT_FLOWS_BY_REAL_ESTATE_ID,
        (row["id"],),
    )
    flow_rows = await cursor.fetchall()
    flows = [await _build_flow(flow_row) for flow_row in flow_rows]

    return RealEstate(
        id=UUID(row["id"]),
        basic_info=BasicInfo(
            name=row["name"],
            photo_url=row["photo_url"],
            is_residence=row["is_residence"],
            is_rented=row["is_rented"],
            bathrooms=row["bathrooms"],
            bedrooms=row["bedrooms"],
        ),
        location=Location(
            address=row["address"],
            cadastral_reference=row["cadastral_reference"],
        ),
        purchase_info=PurchaseInfo(
            date=row["purchase_date"],
            price=Dezimal(row["purchase_price"]),
            expenses=[
                _deserialize_purchase_expense(expense)
                for expense in json.loads(row["purchase_expenses"])
            ],
        ),
        valuation_info=ValuationInfo(
            estimated_market_value=Dezimal(row["estimated_market_value"]),
            valuations=[
                _deserialize_valuation(val) for val in json.loads(row["valuations"])
            ],
            annual_appreciation=Dezimal(row["annual_appreciation"])
            if (row["annual_appreciation"] is not None)
            else None,
        ),
        flows=flows,
        currency=row["currency"],
        rental_data=_deserialize_rental_data(row.get("rental_data"))
        if isinstance(row, dict)
        else _deserialize_rental_data(row["rental_data"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"] if row["updated_at"] else None,
    )


async def _save_flow(cursor, real_estate_id: UUID, flow: RealEstateFlow) -> None:
    await cursor.execute(
        RealEstateQueries.INSERT_FLOW,
        (
            str(real_estate_id),
            str(flow.periodic_flow_id),
            flow.flow_subtype.value,
            flow.description,
            json.dumps(_serialize_payload(flow.payload)),
        ),
    )


class RealEstateRepository(RealEstatePort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def insert(self, real_estate: RealEstate) -> None:
        if real_estate.id is None:
            real_estate.id = uuid4()

        async with self._db_client.tx() as cursor:
            await cursor.execute(
                RealEstateQueries.INSERT_REAL_ESTATE,
                (
                    str(real_estate.id),
                    real_estate.basic_info.name,
                    real_estate.basic_info.photo_url,
                    real_estate.basic_info.is_residence,
                    real_estate.basic_info.is_rented,
                    real_estate.basic_info.bathrooms,
                    real_estate.basic_info.bedrooms,
                    real_estate.location.address,
                    real_estate.location.cadastral_reference,
                    real_estate.purchase_info.date,
                    str(real_estate.purchase_info.price),
                    real_estate.currency,
                    json.dumps(
                        [
                            _serialize_purchase_expense(expense)
                            for expense in real_estate.purchase_info.expenses
                        ]
                    ),
                    str(real_estate.valuation_info.estimated_market_value),
                    str(real_estate.valuation_info.annual_appreciation)
                    if real_estate.valuation_info.annual_appreciation is not None
                    else None,
                    json.dumps(
                        [
                            _serialize_valuation(val)
                            for val in real_estate.valuation_info.valuations
                        ]
                    ),
                    json.dumps(_serialize_rental_data(real_estate.rental_data))
                    if real_estate.rental_data is not None
                    else None,
                    datetime.now(tzlocal()),
                ),
            )

            for flow in real_estate.flows:
                await _save_flow(cursor, real_estate.id, flow)

    async def update(self, real_estate: RealEstate) -> None:
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                RealEstateQueries.UPDATE_REAL_ESTATE,
                (
                    real_estate.basic_info.name,
                    real_estate.basic_info.photo_url,
                    real_estate.basic_info.is_residence,
                    real_estate.basic_info.is_rented,
                    real_estate.basic_info.bathrooms,
                    real_estate.basic_info.bedrooms,
                    real_estate.location.address,
                    real_estate.location.cadastral_reference,
                    real_estate.purchase_info.date,
                    str(real_estate.purchase_info.price),
                    real_estate.currency,
                    json.dumps(
                        [
                            _serialize_purchase_expense(expense)
                            for expense in real_estate.purchase_info.expenses
                        ]
                    ),
                    str(real_estate.valuation_info.estimated_market_value),
                    str(real_estate.valuation_info.annual_appreciation)
                    if real_estate.valuation_info.annual_appreciation is not None
                    else None,
                    json.dumps(
                        [
                            _serialize_valuation(val)
                            for val in real_estate.valuation_info.valuations
                        ]
                    ),
                    json.dumps(_serialize_rental_data(real_estate.rental_data))
                    if real_estate.rental_data is not None
                    else None,
                    datetime.now(tzlocal()),
                    str(real_estate.id),
                ),
            )

            await cursor.execute(
                RealEstateQueries.DELETE_FLOWS_BY_REAL_ESTATE_ID,
                (str(real_estate.id),),
            )
            for flow in real_estate.flows:
                await _save_flow(cursor, real_estate.id, flow)

    async def delete(self, real_estate_id: UUID) -> None:
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                RealEstateQueries.DELETE_BY_ID,
                (str(real_estate_id),),
            )

    async def get_by_id(self, real_estate_id: UUID) -> Optional[RealEstate]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                RealEstateQueries.GET_BY_ID,
                (str(real_estate_id),),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return await _build_real_estate(row, cursor)

    async def get_all(self) -> list[RealEstate]:
        async with self._db_client.read() as cursor:
            await cursor.execute(RealEstateQueries.GET_ALL)
            rows = await cursor.fetchall()
            return [await _build_real_estate(row, cursor) for row in rows]
