import io
import json
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from werkzeug.datastructures import FileStorage

from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.global_position import (
    InterestType,
    Loan,
    LoanType,
    InstallmentFrequency,
)
from domain.fetch_record import DataSource
from domain.real_estate import (
    Amortization,
    BasicInfo,
    CostPayload,
    LoanPayload,
    Location,
    PurchaseInfo,
    RealEstate,
    RealEstateFlow,
    RealEstateFlowSubtype,
    RentalData,
    RentPayload,
    SupplyPayload,
    ValuationInfo,
)

CREATE_URL = "/api/v1/real-estate"
UPDATE_URL = "/api/v1/real-estate"
LIST_URL = "/api/v1/real-estate"
DELETE_URL = "/api/v1/real-estate"

RE_ID = uuid.uuid4()
FLOW_ID_1 = uuid.uuid4()
FLOW_ID_2 = uuid.uuid4()
FLOW_ID_3 = uuid.uuid4()
FLOW_ID_4 = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers: JSON payloads for HTTP requests
# ---------------------------------------------------------------------------


def _base_re_payload(**overrides):
    payload = {
        "basic_info": {"name": "Test House", "is_residence": True, "is_rented": False},
        "location": {"address": "123 Main St"},
        "purchase_info": {"date": "2020-01-15", "price": "200000", "expenses": []},
        "valuation_info": {
            "estimated_market_value": "250000",
            "valuations": [],
        },
        "currency": "EUR",
        "flows": [],
    }
    payload.update(overrides)
    return payload


def _periodic_flow_dict(id=None, name="Mortgage Payment", amount="500", **overrides):
    pf = {
        "name": name,
        "amount": amount,
        "currency": "EUR",
        "flow_type": "EXPENSE",
        "frequency": "MONTHLY",
        "enabled": True,
        "since": "2020-02-01",
    }
    if id:
        pf["id"] = str(id)
    pf.update(overrides)
    return pf


def _loan_flow_payload(linked_loan_hash=None, pf_id=None, **overrides):
    flow = {
        "flow_subtype": "LOAN",
        "description": "Main loan",
        "periodic_flow": _periodic_flow_dict(id=pf_id),
    }
    if pf_id:
        flow["periodic_flow_id"] = str(pf_id)
    if linked_loan_hash:
        flow["payload"] = {"linked_loan_hash": linked_loan_hash, "type": "MORTGAGE"}
    else:
        flow["payload"] = {
            "type": "MORTGAGE",
            "loan_amount": "200000",
            "interest_rate": "0.03",
            "interest_type": "FIXED",
            "principal_outstanding": "180000",
        }
    flow.update(overrides)
    return flow


def _rent_flow_payload(pf_id=None, **overrides):
    flow = {
        "flow_subtype": "RENT",
        "description": "Rental income",
        "payload": {},
        "periodic_flow": _periodic_flow_dict(
            id=pf_id, name="Rent Income", amount="800", flow_type="EARNING"
        ),
    }
    if pf_id:
        flow["periodic_flow_id"] = str(pf_id)
    flow.update(overrides)
    return flow


def _supply_flow_payload(tax_deductible=False, pf_id=None, **overrides):
    flow = {
        "flow_subtype": "SUPPLY",
        "description": "Water bill",
        "payload": {"tax_deductible": tax_deductible},
        "periodic_flow": _periodic_flow_dict(id=pf_id, name="Water", amount="50"),
    }
    if pf_id:
        flow["periodic_flow_id"] = str(pf_id)
    flow.update(overrides)
    return flow


def _cost_flow_payload(tax_deductible=False, pf_id=None, **overrides):
    flow = {
        "flow_subtype": "COST",
        "description": "Maintenance",
        "payload": {"tax_deductible": tax_deductible},
        "periodic_flow": _periodic_flow_dict(
            id=pf_id, name="Maintenance", amount="100"
        ),
    }
    if pf_id:
        flow["periodic_flow_id"] = str(pf_id)
    flow.update(overrides)
    return flow


# ---------------------------------------------------------------------------
# Helpers: domain objects for mocking port returns
# ---------------------------------------------------------------------------


def _make_periodic_flow(id=None, name="Mortgage Payment", amount=Dezimal(500)):
    return PeriodicFlow(
        id=id or uuid.uuid4(),
        name=name,
        amount=amount,
        currency="EUR",
        flow_type=FlowType.EXPENSE,
        frequency=FlowFrequency.MONTHLY,
        category=None,
        enabled=True,
        since=date(2020, 2, 1),
        until=None,
        icon=None,
    )


def _make_stored_flow(periodic_flow_id, subtype, payload, periodic_flow=None):
    return RealEstateFlow(
        periodic_flow_id=periodic_flow_id,
        periodic_flow=periodic_flow,
        flow_subtype=subtype,
        description="Test flow",
        payload=payload,
    )


def _make_stored_re(
    id=None,
    flows=None,
    photo_url=None,
    currency="EUR",
    rental_data=None,
    name="Test House",
):
    return RealEstate(
        id=id or RE_ID,
        basic_info=BasicInfo(
            name=name,
            is_residence=True,
            is_rented=False,
            photo_url=photo_url,
        ),
        location=Location(address="123 Main St"),
        purchase_info=PurchaseInfo(
            date=date(2020, 1, 15),
            price=Dezimal(200000),
            expenses=[],
        ),
        valuation_info=ValuationInfo(
            estimated_market_value=Dezimal(250000),
            valuations=[],
        ),
        flows=flows or [],
        currency=currency,
        rental_data=rental_data,
        created_at=datetime(2020, 1, 15, 10, 0, 0),
        updated_at=None,
    )


def _make_loan(hash_val="hash1"):
    return Loan(
        id=uuid.uuid4(),
        type=LoanType.MORTGAGE,
        currency="EUR",
        current_installment=Dezimal(800),
        interest_rate=Dezimal("0.025"),
        loan_amount=Dezimal(250000),
        creation=date(2020, 1, 1),
        maturity=date(2050, 1, 1),
        principal_outstanding=Dezimal(230000),
        interest_type=InterestType.VARIABLE,
        installment_frequency=InstallmentFrequency.MONTHLY,
        installment_interests=Dezimal(450),
        euribor_rate=Dezimal("0.035"),
        fixed_years=2,
        fixed_interest_rate=Dezimal("0.02"),
        hash=hash_val,
        source=DataSource.REAL,
    )


# ---------------------------------------------------------------------------
# Helpers: HTTP wrappers
# ---------------------------------------------------------------------------


async def _create_re(client, payload, photo_bytes=None):
    files = {}
    if photo_bytes:
        files["photo"] = FileStorage(
            stream=io.BytesIO(photo_bytes),
            filename="house.jpg",
            content_type="image/jpeg",
        )
    return await client.post(
        CREATE_URL,
        form={"data": json.dumps(payload)},
        files=files,
    )


async def _update_re_json(client, payload):
    return await client.put(UPDATE_URL, json=payload)


async def _update_re_multipart(client, payload, photo_bytes=None):
    files = {}
    if photo_bytes:
        files["photo"] = FileStorage(
            stream=io.BytesIO(photo_bytes),
            filename="house.jpg",
            content_type="image/jpeg",
        )
    return await client.put(
        UPDATE_URL,
        form={"data": json.dumps(payload)},
        files=files,
    )


# ---------------------------------------------------------------------------
# Mock setup helper
# ---------------------------------------------------------------------------


def _setup_pf_save(periodic_flow_port, ids=None):
    """Configure periodic_flow_port.save to return PeriodicFlows with given IDs."""
    if ids is None:
        ids = [uuid.uuid4()]
    returns = [_make_periodic_flow(id=fid) for fid in ids]
    periodic_flow_port.save = AsyncMock(side_effect=returns)


# =========================================================================
# CREATE VALIDATION
# =========================================================================


class TestCreateValidation:
    @pytest.mark.asyncio
    async def test_create_without_multipart_returns_400(self, client):
        response = await client.post(CREATE_URL, json=_base_re_payload())
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"
        assert "multipart/form-data" in body["message"]

    @pytest.mark.asyncio
    async def test_create_multipart_missing_data_field_returns_400(self, client):
        response = await client.post(CREATE_URL, form={"other": "value"}, files={})
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"
        assert "Missing 'data' field" in body["message"]

    @pytest.mark.asyncio
    async def test_create_multipart_invalid_json_returns_400(self, client):
        response = await client.post(
            CREATE_URL, form={"data": "not valid json {"}, files={}
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"
        assert "Invalid JSON" in body["message"]

    @pytest.mark.asyncio
    async def test_create_missing_required_fields_returns_400(self, client):
        payload = {"basic_info": {}}  # missing 'name'
        response = await _create_re(client, payload)
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"

    @pytest.mark.asyncio
    async def test_create_invalid_flow_subtype_returns_400(self, client):
        payload = _base_re_payload(
            flows=[
                {
                    "flow_subtype": "INVALID",
                    "description": "Bad",
                    "payload": {},
                    "periodic_flow": _periodic_flow_dict(),
                }
            ]
        )
        response = await _create_re(client, payload)
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"


# =========================================================================
# CREATE BASIC
# =========================================================================


class TestCreateBasic:
    @pytest.mark.asyncio
    async def test_create_minimal_no_flows_no_photo(
        self, client, real_estate_port, periodic_flow_port, file_storage_port
    ):
        response = await _create_re(client, _base_re_payload())
        assert response.status_code == 201
        real_estate_port.insert.assert_awaited_once()
        periodic_flow_port.save.assert_not_awaited()
        file_storage_port.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_with_photo_upload(
        self, client, real_estate_port, file_storage_port
    ):
        file_storage_port.save = AsyncMock(return_value="real_estate/abc.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/abc.jpg"
        )

        response = await _create_re(client, _base_re_payload(), photo_bytes=b"fake-img")
        assert response.status_code == 201
        file_storage_port.save.assert_awaited_once()
        inserted = real_estate_port.insert.await_args[0][0]
        assert inserted.basic_info.photo_url == "/static/real_estate/abc.jpg"

    @pytest.mark.asyncio
    async def test_create_with_all_optional_fields(self, client, real_estate_port):
        payload = _base_re_payload(
            basic_info={
                "name": "Villa",
                "is_residence": False,
                "is_rented": True,
                "bathrooms": 3,
                "bedrooms": 5,
            },
            location={"address": "456 Oak Ave", "cadastral_reference": "CAD-123"},
            purchase_info={
                "date": "2019-06-01",
                "price": "500000",
                "expenses": [
                    {
                        "concept": "Notary",
                        "amount": "2000",
                        "description": "Notary fees",
                    }
                ],
            },
            valuation_info={
                "estimated_market_value": "600000",
                "annual_appreciation": "0.02",
                "valuations": [
                    {"date": "2023-01-01", "amount": "550000", "notes": "Appraisal"}
                ],
            },
            rental_data={
                "marginal_tax_rate": 24,
                "vacancy_rate": 5,
                "amortizations": [
                    {
                        "concept": "Building",
                        "base_amount": "400000",
                        "amount": "12000",
                        "percentage": "3",
                    }
                ],
            },
        )
        response = await _create_re(client, payload)
        assert response.status_code == 201
        inserted = real_estate_port.insert.await_args[0][0]
        assert inserted.basic_info.bathrooms == 3
        assert inserted.basic_info.bedrooms == 5
        assert inserted.location.cadastral_reference == "CAD-123"
        assert len(inserted.purchase_info.expenses) == 1
        assert len(inserted.valuation_info.valuations) == 1
        assert inserted.rental_data is not None
        assert len(inserted.rental_data.amortizations) == 1


# =========================================================================
# CREATE WITH FLOWS
# =========================================================================


class TestCreateWithFlows:
    @pytest.mark.asyncio
    async def test_create_single_unlinked_loan(
        self, client, real_estate_port, periodic_flow_port
    ):
        _setup_pf_save(periodic_flow_port, [FLOW_ID_1])
        payload = _base_re_payload(flows=[_loan_flow_payload()])
        response = await _create_re(client, payload)
        assert response.status_code == 201
        periodic_flow_port.save.assert_awaited_once()

        inserted = real_estate_port.insert.await_args[0][0]
        assert len(inserted.flows) == 1
        assert inserted.flows[0].periodic_flow_id == FLOW_ID_1
        assert isinstance(inserted.flows[0].payload, LoanPayload)
        assert inserted.flows[0].payload.loan_amount == Dezimal(200000)
        assert inserted.flows[0].payload.linked_loan_hash is None

    @pytest.mark.asyncio
    async def test_create_single_linked_loan(
        self, client, real_estate_port, periodic_flow_port, position_port
    ):
        _setup_pf_save(periodic_flow_port, [FLOW_ID_1])
        payload = _base_re_payload(flows=[_loan_flow_payload(linked_loan_hash="hash1")])
        response = await _create_re(client, payload)
        assert response.status_code == 201

        inserted = real_estate_port.insert.await_args[0][0]
        loan_payload = inserted.flows[0].payload
        assert loan_payload.linked_loan_hash == "hash1"
        assert loan_payload.loan_amount is None
        assert loan_payload.interest_rate == Dezimal(0)

        # Verify list injects linked loan data
        stored = _make_stored_re(
            flows=[
                _make_stored_flow(
                    FLOW_ID_1,
                    RealEstateFlowSubtype.LOAN,
                    LoanPayload(
                        type=LoanType.MORTGAGE,
                        loan_amount=None,
                        interest_rate=Dezimal(0),
                        euribor_rate=None,
                        interest_type=InterestType.FIXED,
                        fixed_years=None,
                        principal_outstanding=Dezimal(0),
                        linked_loan_hash="hash1",
                    ),
                )
            ]
        )
        real_estate_port.get_all = AsyncMock(return_value=[stored])
        position_port.get_loans_by_hash = AsyncMock(
            return_value={"hash1": _make_loan("hash1")}
        )

        list_resp = await client.get(LIST_URL)
        assert list_resp.status_code == 200
        data = await list_resp.get_json()
        loan_data = data[0]["flows"][0]["payload"]
        assert loan_data["loan_amount"] == 250000
        assert loan_data["interest_rate"] == pytest.approx(0.025)
        assert loan_data["linked_loan_hash"] == "hash1"

    @pytest.mark.asyncio
    async def test_create_rent_flow(self, client, real_estate_port, periodic_flow_port):
        _setup_pf_save(periodic_flow_port, [FLOW_ID_1])
        payload = _base_re_payload(flows=[_rent_flow_payload()])
        response = await _create_re(client, payload)
        assert response.status_code == 201
        inserted = real_estate_port.insert.await_args[0][0]
        assert inserted.flows[0].flow_subtype == RealEstateFlowSubtype.RENT
        assert isinstance(inserted.flows[0].payload, RentPayload)

    @pytest.mark.asyncio
    async def test_create_supply_flow(
        self, client, real_estate_port, periodic_flow_port
    ):
        _setup_pf_save(periodic_flow_port, [FLOW_ID_1])
        payload = _base_re_payload(flows=[_supply_flow_payload(tax_deductible=True)])
        response = await _create_re(client, payload)
        assert response.status_code == 201
        inserted = real_estate_port.insert.await_args[0][0]
        assert isinstance(inserted.flows[0].payload, SupplyPayload)
        assert inserted.flows[0].payload.tax_deductible is True

    @pytest.mark.asyncio
    async def test_create_cost_flow(self, client, real_estate_port, periodic_flow_port):
        _setup_pf_save(periodic_flow_port, [FLOW_ID_1])
        payload = _base_re_payload(flows=[_cost_flow_payload(tax_deductible=False)])
        response = await _create_re(client, payload)
        assert response.status_code == 201
        inserted = real_estate_port.insert.await_args[0][0]
        assert isinstance(inserted.flows[0].payload, CostPayload)
        assert inserted.flows[0].payload.tax_deductible is False

    @pytest.mark.asyncio
    async def test_create_mixed_flows(
        self, client, real_estate_port, periodic_flow_port
    ):
        _setup_pf_save(periodic_flow_port, [FLOW_ID_1, FLOW_ID_2, FLOW_ID_3, FLOW_ID_4])
        payload = _base_re_payload(
            flows=[
                _loan_flow_payload(),
                _rent_flow_payload(),
                _supply_flow_payload(),
                _cost_flow_payload(),
            ]
        )
        response = await _create_re(client, payload)
        assert response.status_code == 201
        assert periodic_flow_port.save.await_count == 4

        inserted = real_estate_port.insert.await_args[0][0]
        subtypes = {f.flow_subtype for f in inserted.flows}
        assert subtypes == {
            RealEstateFlowSubtype.LOAN,
            RealEstateFlowSubtype.RENT,
            RealEstateFlowSubtype.SUPPLY,
            RealEstateFlowSubtype.COST,
        }


# =========================================================================
# CREATE WITH EXISTING FLOWS
# =========================================================================


class TestCreateWithExistingFlows:
    @pytest.mark.asyncio
    async def test_existing_flow_updates_it(
        self, client, real_estate_port, periodic_flow_port
    ):
        existing_pf = _make_periodic_flow(id=FLOW_ID_1)
        periodic_flow_port.get_by_id = AsyncMock(return_value=existing_pf)

        payload = _base_re_payload(flows=[_loan_flow_payload(pf_id=FLOW_ID_1)])
        response = await _create_re(client, payload)
        assert response.status_code == 201
        periodic_flow_port.get_by_id.assert_awaited_once()
        periodic_flow_port.update.assert_awaited_once()
        periodic_flow_port.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_existing_flow_not_found_returns_400(
        self, client, periodic_flow_port
    ):
        periodic_flow_port.get_by_id = AsyncMock(return_value=None)
        payload = _base_re_payload(flows=[_loan_flow_payload(pf_id=FLOW_ID_1)])
        response = await _create_re(client, payload)
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"


# =========================================================================
# UPDATE VALIDATION
# =========================================================================


class TestUpdateValidation:
    @pytest.mark.asyncio
    async def test_update_missing_id_returns_400(self, client):
        payload = _base_re_payload()
        response = await _update_re_json(client, payload)
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"
        assert "ID is required" in body["message"]

    @pytest.mark.asyncio
    async def test_update_invalid_id_format_returns_400(self, client):
        payload = _base_re_payload(id="not-a-uuid")
        response = await _update_re_json(client, payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_multipart_missing_data_returns_400(self, client):
        response = await client.put(UPDATE_URL, form={"other": "val"}, files={})
        assert response.status_code == 400
        body = await response.get_json()
        assert "Missing 'data' field" in body["message"]

    @pytest.mark.asyncio
    async def test_update_multipart_invalid_json_returns_400(self, client):
        response = await client.put(UPDATE_URL, form={"data": "{bad json"}, files={})
        assert response.status_code == 400
        body = await response.get_json()
        assert "Invalid JSON" in body["message"]

    @pytest.mark.asyncio
    async def test_update_nonexistent_re_returns_404(self, client, real_estate_port):
        real_estate_port.get_by_id = AsyncMock(return_value=None)
        payload = _base_re_payload(id=str(RE_ID))
        response = await _update_re_json(client, payload)
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "NOT_FOUND"


# =========================================================================
# UPDATE BASIC
# =========================================================================


class TestUpdateBasic:
    @pytest.mark.asyncio
    async def test_update_via_json(self, client, real_estate_port):
        real_estate_port.get_by_id = AsyncMock(return_value=_make_stored_re())
        payload = _base_re_payload(id=str(RE_ID))
        response = await _update_re_json(client, payload)
        assert response.status_code == 204
        real_estate_port.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_via_multipart(self, client, real_estate_port):
        real_estate_port.get_by_id = AsyncMock(return_value=_make_stored_re())
        payload = _base_re_payload(id=str(RE_ID))
        response = await _update_re_multipart(client, payload)
        assert response.status_code == 204
        real_estate_port.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_preserves_currency(self, client, real_estate_port):
        real_estate_port.get_by_id = AsyncMock(
            return_value=_make_stored_re(currency="USD")
        )
        payload = _base_re_payload(id=str(RE_ID), currency="EUR")
        response = await _update_re_json(client, payload)
        assert response.status_code == 204
        updated = real_estate_port.update.await_args[0][0]
        assert updated.currency == "USD"

    @pytest.mark.asyncio
    async def test_update_preserves_photo_when_no_upload(
        self, client, real_estate_port
    ):
        real_estate_port.get_by_id = AsyncMock(
            return_value=_make_stored_re(photo_url="/static/real_estate/old.jpg")
        )
        payload = _base_re_payload(id=str(RE_ID))
        response = await _update_re_json(client, payload)
        assert response.status_code == 204
        updated = real_estate_port.update.await_args[0][0]
        assert updated.basic_info.photo_url == "/static/real_estate/old.jpg"


# =========================================================================
# UPDATE PHOTO HANDLING
# =========================================================================


class TestUpdatePhotoHandling:
    @pytest.mark.asyncio
    async def test_update_replaces_photo(
        self, client, real_estate_port, file_storage_port
    ):
        real_estate_port.get_by_id = AsyncMock(
            return_value=_make_stored_re(photo_url="/static/real_estate/old.jpg")
        )
        file_storage_port.save = AsyncMock(return_value="real_estate/new.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/new.jpg"
        )

        payload = _base_re_payload(id=str(RE_ID))
        response = await _update_re_multipart(client, payload, photo_bytes=b"new-img")
        assert response.status_code == 204
        file_storage_port.save.assert_awaited_once()
        # Verify existing_url was passed
        call_kwargs = file_storage_port.save.await_args
        assert call_kwargs.kwargs.get("existing_url") == "/static/real_estate/old.jpg"

    @pytest.mark.asyncio
    async def test_update_adds_photo_to_re_without_photo(
        self, client, real_estate_port, file_storage_port
    ):
        real_estate_port.get_by_id = AsyncMock(
            return_value=_make_stored_re(photo_url=None)
        )
        file_storage_port.save = AsyncMock(return_value="real_estate/first.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/first.jpg"
        )

        payload = _base_re_payload(id=str(RE_ID))
        response = await _update_re_multipart(client, payload, photo_bytes=b"img")
        assert response.status_code == 204
        updated = real_estate_port.update.await_args[0][0]
        assert updated.basic_info.photo_url == "/static/real_estate/first.jpg"


# =========================================================================
# UPDATE FLOWS
# =========================================================================


class TestUpdateFlows:
    @pytest.mark.asyncio
    async def test_update_adds_new_flow(
        self, client, real_estate_port, periodic_flow_port
    ):
        real_estate_port.get_by_id = AsyncMock(return_value=_make_stored_re(flows=[]))
        _setup_pf_save(periodic_flow_port, [FLOW_ID_1])

        payload = _base_re_payload(id=str(RE_ID), flows=[_rent_flow_payload()])
        response = await _update_re_json(client, payload)
        assert response.status_code == 204
        periodic_flow_port.save.assert_awaited_once()
        updated = real_estate_port.update.await_args[0][0]
        assert len(updated.flows) == 1
        assert updated.flows[0].periodic_flow_id == FLOW_ID_1

    @pytest.mark.asyncio
    async def test_update_removes_unassigned_flow_when_true(
        self, client, real_estate_port, periodic_flow_port
    ):
        existing_pf = _make_periodic_flow(id=FLOW_ID_1)
        existing_re = _make_stored_re(
            flows=[
                _make_stored_flow(FLOW_ID_1, RealEstateFlowSubtype.RENT, RentPayload()),
                _make_stored_flow(
                    FLOW_ID_2, RealEstateFlowSubtype.SUPPLY, SupplyPayload()
                ),
            ]
        )
        real_estate_port.get_by_id = AsyncMock(return_value=existing_re)
        periodic_flow_port.get_by_id = AsyncMock(return_value=existing_pf)

        # Only keep FLOW_ID_1, remove FLOW_ID_2
        payload = _base_re_payload(
            id=str(RE_ID),
            remove_unassigned_flows=True,
            flows=[_rent_flow_payload(pf_id=FLOW_ID_1)],
        )
        response = await _update_re_json(client, payload)
        assert response.status_code == 204
        periodic_flow_port.delete.assert_awaited_once_with(FLOW_ID_2)

    @pytest.mark.asyncio
    async def test_update_keeps_unassigned_flow_when_false(
        self, client, real_estate_port, periodic_flow_port
    ):
        existing_pf = _make_periodic_flow(id=FLOW_ID_1)
        existing_re = _make_stored_re(
            flows=[
                _make_stored_flow(FLOW_ID_1, RealEstateFlowSubtype.RENT, RentPayload()),
                _make_stored_flow(
                    FLOW_ID_2, RealEstateFlowSubtype.SUPPLY, SupplyPayload()
                ),
            ]
        )
        real_estate_port.get_by_id = AsyncMock(return_value=existing_re)
        periodic_flow_port.get_by_id = AsyncMock(return_value=existing_pf)

        payload = _base_re_payload(
            id=str(RE_ID),
            remove_unassigned_flows=False,
            flows=[_rent_flow_payload(pf_id=FLOW_ID_1)],
        )
        response = await _update_re_json(client, payload)
        assert response.status_code == 204
        periodic_flow_port.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_loan_unlinked_to_linked(
        self, client, real_estate_port, periodic_flow_port
    ):
        existing_pf = _make_periodic_flow(id=FLOW_ID_1)
        existing_re = _make_stored_re(
            flows=[
                _make_stored_flow(
                    FLOW_ID_1,
                    RealEstateFlowSubtype.LOAN,
                    LoanPayload(
                        type=LoanType.MORTGAGE,
                        loan_amount=Dezimal(200000),
                        interest_rate=Dezimal("0.03"),
                        euribor_rate=None,
                        interest_type=InterestType.FIXED,
                        fixed_years=None,
                        principal_outstanding=Dezimal(180000),
                    ),
                )
            ]
        )
        real_estate_port.get_by_id = AsyncMock(return_value=existing_re)
        periodic_flow_port.get_by_id = AsyncMock(return_value=existing_pf)

        payload = _base_re_payload(
            id=str(RE_ID),
            flows=[_loan_flow_payload(linked_loan_hash="link1", pf_id=FLOW_ID_1)],
        )
        response = await _update_re_json(client, payload)
        assert response.status_code == 204
        updated = real_estate_port.update.await_args[0][0]
        loan_p = updated.flows[0].payload
        assert loan_p.linked_loan_hash == "link1"
        assert loan_p.loan_amount is None

    @pytest.mark.asyncio
    async def test_update_loan_linked_to_unlinked(
        self, client, real_estate_port, periodic_flow_port
    ):
        existing_pf = _make_periodic_flow(id=FLOW_ID_1)
        existing_re = _make_stored_re(
            flows=[
                _make_stored_flow(
                    FLOW_ID_1,
                    RealEstateFlowSubtype.LOAN,
                    LoanPayload(
                        type=LoanType.MORTGAGE,
                        loan_amount=None,
                        interest_rate=Dezimal(0),
                        euribor_rate=None,
                        interest_type=InterestType.FIXED,
                        fixed_years=None,
                        principal_outstanding=Dezimal(0),
                        linked_loan_hash="link1",
                    ),
                )
            ]
        )
        real_estate_port.get_by_id = AsyncMock(return_value=existing_re)
        periodic_flow_port.get_by_id = AsyncMock(return_value=existing_pf)

        payload = _base_re_payload(
            id=str(RE_ID),
            flows=[_loan_flow_payload(pf_id=FLOW_ID_1)],  # no linked_loan_hash
        )
        response = await _update_re_json(client, payload)
        assert response.status_code == 204
        updated = real_estate_port.update.await_args[0][0]
        loan_p = updated.flows[0].payload
        assert loan_p.linked_loan_hash is None
        assert loan_p.loan_amount == Dezimal(200000)


# =========================================================================
# UPDATE RENTAL DATA
# =========================================================================


class TestUpdateRentalData:
    @pytest.mark.asyncio
    async def test_update_preserves_rental_data_when_omitted(
        self, client, real_estate_port
    ):
        existing_rental = RentalData(
            amortizations=[
                Amortization(
                    concept="Building",
                    base_amount=Dezimal(400000),
                    amount=Dezimal(12000),
                    percentage=Dezimal(3),
                )
            ],
            marginal_tax_rate=Dezimal(24),
            vacancy_rate=Dezimal(5),
        )
        real_estate_port.get_by_id = AsyncMock(
            return_value=_make_stored_re(rental_data=existing_rental)
        )
        payload = _base_re_payload(id=str(RE_ID))
        # No rental_data in payload
        response = await _update_re_json(client, payload)
        assert response.status_code == 204
        updated = real_estate_port.update.await_args[0][0]
        assert updated.rental_data is not None
        assert updated.rental_data.marginal_tax_rate == Dezimal(24)

    @pytest.mark.asyncio
    async def test_update_replaces_rental_data_when_sent(
        self, client, real_estate_port
    ):
        real_estate_port.get_by_id = AsyncMock(return_value=_make_stored_re())
        payload = _base_re_payload(
            id=str(RE_ID),
            rental_data={
                "marginal_tax_rate": 30,
                "vacancy_rate": 10,
                "amortizations": [],
            },
        )
        response = await _update_re_json(client, payload)
        assert response.status_code == 204
        updated = real_estate_port.update.await_args[0][0]
        assert updated.rental_data is not None
        assert updated.rental_data.marginal_tax_rate == Dezimal(30)


# =========================================================================
# DELETE VALIDATION
# =========================================================================


class TestDeleteValidation:
    @pytest.mark.asyncio
    async def test_delete_invalid_uuid_returns_400(self, client):
        response = await client.delete(f"{DELETE_URL}/not-a-uuid")
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client, real_estate_port):
        real_estate_port.get_by_id = AsyncMock(return_value=None)
        response = await client.delete(f"{DELETE_URL}/{RE_ID}")
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "NOT_FOUND"


# =========================================================================
# DELETE BASIC
# =========================================================================


class TestDeleteBasic:
    @pytest.mark.asyncio
    async def test_delete_no_flows_no_photo(
        self, client, real_estate_port, periodic_flow_port, file_storage_port
    ):
        real_estate_port.get_by_id = AsyncMock(
            return_value=_make_stored_re(flows=[], photo_url=None)
        )
        response = await client.delete(f"{DELETE_URL}/{RE_ID}")
        assert response.status_code == 204
        real_estate_port.delete.assert_awaited_once_with(RE_ID)
        periodic_flow_port.delete.assert_not_awaited()
        file_storage_port.delete_by_url.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_with_photo_cleans_up(
        self, client, real_estate_port, file_storage_port
    ):
        real_estate_port.get_by_id = AsyncMock(
            return_value=_make_stored_re(photo_url="/static/real_estate/pic.jpg")
        )
        response = await client.delete(f"{DELETE_URL}/{RE_ID}")
        assert response.status_code == 204
        file_storage_port.delete_by_url.assert_awaited_once_with(
            "/static/real_estate/pic.jpg"
        )

    @pytest.mark.asyncio
    async def test_delete_remove_related_flows_true(
        self, client, real_estate_port, periodic_flow_port
    ):
        real_estate_port.get_by_id = AsyncMock(
            return_value=_make_stored_re(
                flows=[
                    _make_stored_flow(
                        FLOW_ID_1,
                        RealEstateFlowSubtype.LOAN,
                        LoanPayload(
                            type=LoanType.MORTGAGE,
                            loan_amount=Dezimal(200000),
                            interest_rate=Dezimal("0.03"),
                            euribor_rate=None,
                            interest_type=InterestType.FIXED,
                            fixed_years=None,
                            principal_outstanding=Dezimal(180000),
                        ),
                    ),
                    _make_stored_flow(
                        FLOW_ID_2, RealEstateFlowSubtype.RENT, RentPayload()
                    ),
                ]
            )
        )
        response = await client.delete(
            f"{DELETE_URL}/{RE_ID}",
            json={"remove_related_flows": True},
        )
        assert response.status_code == 204
        assert periodic_flow_port.delete.await_count == 2

    @pytest.mark.asyncio
    async def test_delete_remove_related_flows_false(
        self, client, real_estate_port, periodic_flow_port
    ):
        real_estate_port.get_by_id = AsyncMock(
            return_value=_make_stored_re(
                flows=[
                    _make_stored_flow(
                        FLOW_ID_1, RealEstateFlowSubtype.RENT, RentPayload()
                    ),
                ]
            )
        )
        response = await client.delete(f"{DELETE_URL}/{RE_ID}")
        assert response.status_code == 204
        periodic_flow_port.delete.assert_not_awaited()


# =========================================================================
# LIST BASIC
# =========================================================================


class TestListBasic:
    @pytest.mark.asyncio
    async def test_list_empty(self, client, real_estate_port):
        real_estate_port.get_all = AsyncMock(return_value=[])
        response = await client.get(LIST_URL)
        assert response.status_code == 200
        data = await response.get_json()
        assert data == []

    @pytest.mark.asyncio
    async def test_list_single_basic_serialization(self, client, real_estate_port):
        real_estate_port.get_all = AsyncMock(return_value=[_make_stored_re()])
        response = await client.get(LIST_URL)
        assert response.status_code == 200
        data = await response.get_json()
        assert len(data) == 1
        item = data[0]
        assert item["id"] == str(RE_ID)
        assert item["basic_info"]["name"] == "Test House"
        assert item["location"]["address"] == "123 Main St"
        assert item["purchase_info"]["date"] == "2020-01-15"
        assert item["currency"] == "EUR"
        assert item["created_at"] is not None
        assert item["flows"] == []
        assert item["rental_data"] is None

    @pytest.mark.asyncio
    async def test_list_multiple(self, client, real_estate_port):
        re1 = _make_stored_re(id=uuid.uuid4(), name="House A")
        re2 = _make_stored_re(id=uuid.uuid4(), name="House B")
        real_estate_port.get_all = AsyncMock(return_value=[re1, re2])
        response = await client.get(LIST_URL)
        assert response.status_code == 200
        data = await response.get_json()
        assert len(data) == 2
        names = {d["basic_info"]["name"] for d in data}
        assert names == {"House A", "House B"}

    @pytest.mark.asyncio
    async def test_list_rental_data_serialization(self, client, real_estate_port):
        rental = RentalData(
            amortizations=[
                Amortization(
                    concept="Building",
                    base_amount=Dezimal(400000),
                    amount=Dezimal(12000),
                    percentage=Dezimal(3),
                )
            ],
            marginal_tax_rate=Dezimal(24),
            vacancy_rate=Dezimal(5),
        )
        real_estate_port.get_all = AsyncMock(
            return_value=[_make_stored_re(rental_data=rental)]
        )
        response = await client.get(LIST_URL)
        assert response.status_code == 200
        data = await response.get_json()
        rd = data[0]["rental_data"]
        assert rd is not None
        assert rd["marginal_tax_rate"] == 24
        assert rd["vacancy_rate"] == 5
        assert len(rd["amortizations"]) == 1
        assert rd["amortizations"][0]["concept"] == "Building"


# =========================================================================
# LIST LINKED LOAN INJECTION
# =========================================================================


class TestListLinkedLoanInjection:
    @pytest.mark.asyncio
    async def test_list_injects_linked_loan_data(
        self, client, real_estate_port, position_port
    ):
        stored = _make_stored_re(
            flows=[
                _make_stored_flow(
                    FLOW_ID_1,
                    RealEstateFlowSubtype.LOAN,
                    LoanPayload(
                        type=LoanType.MORTGAGE,
                        loan_amount=None,
                        interest_rate=Dezimal(0),
                        euribor_rate=None,
                        interest_type=InterestType.FIXED,
                        fixed_years=None,
                        principal_outstanding=Dezimal(0),
                        linked_loan_hash="hash1",
                    ),
                )
            ]
        )
        real_estate_port.get_all = AsyncMock(return_value=[stored])
        loan = _make_loan("hash1")
        position_port.get_loans_by_hash = AsyncMock(return_value={"hash1": loan})

        response = await client.get(LIST_URL)
        assert response.status_code == 200
        data = await response.get_json()
        payload = data[0]["flows"][0]["payload"]
        assert payload["loan_amount"] == 250000
        assert payload["principal_outstanding"] == 230000
        assert payload["interest_type"] == "VARIABLE"
        assert payload["euribor_rate"] == pytest.approx(0.035)
        assert payload["monthly_interests"] == 450
        assert payload["linked_loan_hash"] == "hash1"

    @pytest.mark.asyncio
    async def test_list_linked_loan_not_found_keeps_stub(
        self, client, real_estate_port, position_port
    ):
        stored = _make_stored_re(
            flows=[
                _make_stored_flow(
                    FLOW_ID_1,
                    RealEstateFlowSubtype.LOAN,
                    LoanPayload(
                        type=LoanType.MORTGAGE,
                        loan_amount=None,
                        interest_rate=Dezimal(0),
                        euribor_rate=None,
                        interest_type=InterestType.FIXED,
                        fixed_years=None,
                        principal_outstanding=Dezimal(0),
                        linked_loan_hash="missing_hash",
                    ),
                )
            ]
        )
        real_estate_port.get_all = AsyncMock(return_value=[stored])
        position_port.get_loans_by_hash = AsyncMock(return_value={})

        response = await client.get(LIST_URL)
        assert response.status_code == 200
        data = await response.get_json()
        payload = data[0]["flows"][0]["payload"]
        assert payload["loan_amount"] is None
        assert payload["interest_rate"] == 0
        assert payload["linked_loan_hash"] == "missing_hash"

    @pytest.mark.asyncio
    async def test_list_mixed_linked_and_unlinked(
        self, client, real_estate_port, position_port
    ):
        stored = _make_stored_re(
            flows=[
                _make_stored_flow(
                    FLOW_ID_1,
                    RealEstateFlowSubtype.LOAN,
                    LoanPayload(
                        type=LoanType.MORTGAGE,
                        loan_amount=None,
                        interest_rate=Dezimal(0),
                        euribor_rate=None,
                        interest_type=InterestType.FIXED,
                        fixed_years=None,
                        principal_outstanding=Dezimal(0),
                        linked_loan_hash="hash1",
                    ),
                ),
                _make_stored_flow(
                    FLOW_ID_2,
                    RealEstateFlowSubtype.LOAN,
                    LoanPayload(
                        type=LoanType.STANDARD,
                        loan_amount=Dezimal(100000),
                        interest_rate=Dezimal("0.05"),
                        euribor_rate=None,
                        interest_type=InterestType.FIXED,
                        fixed_years=None,
                        principal_outstanding=Dezimal(90000),
                    ),
                ),
            ]
        )
        real_estate_port.get_all = AsyncMock(return_value=[stored])
        loan = _make_loan("hash1")
        position_port.get_loans_by_hash = AsyncMock(return_value={"hash1": loan})

        response = await client.get(LIST_URL)
        data = await response.get_json()
        flows = data[0]["flows"]

        # Find linked and unlinked
        linked = next(
            f for f in flows if f["payload"].get("linked_loan_hash") == "hash1"
        )
        unlinked = next(f for f in flows if "linked_loan_hash" not in f["payload"])

        # Linked got injected
        assert linked["payload"]["loan_amount"] == 250000
        # Unlinked kept original values
        assert unlinked["payload"]["loan_amount"] == 100000
        assert unlinked["payload"]["interest_rate"] == pytest.approx(0.05)


# =========================================================================
# FULL CRUD LIFECYCLE
# =========================================================================


class TestFullCrudLifecycle:
    @pytest.mark.asyncio
    async def test_lifecycle_basic(self, client, real_estate_port, periodic_flow_port):
        # --- CREATE ---
        _setup_pf_save(periodic_flow_port, [FLOW_ID_1])
        payload = _base_re_payload(flows=[_loan_flow_payload()])
        response = await _create_re(client, payload)
        assert response.status_code == 201

        inserted = real_estate_port.insert.await_args[0][0]
        # Create assigns no ID (port does), so set one for further operations
        re_id = uuid.uuid4()
        inserted.id = re_id
        inserted.created_at = datetime(2020, 1, 15, 10, 0, 0)

        # --- LIST after create ---
        real_estate_port.get_all = AsyncMock(return_value=[inserted])
        list_resp = await client.get(LIST_URL)
        data = await list_resp.get_json()
        assert len(data) == 1
        assert data[0]["basic_info"]["name"] == "Test House"
        assert len(data[0]["flows"]) == 1

        # --- UPDATE ---
        real_estate_port.get_by_id = AsyncMock(return_value=inserted)
        new_rent_pf = _make_periodic_flow(
            id=FLOW_ID_2, name="Rent", amount=Dezimal(800)
        )
        periodic_flow_port.save = AsyncMock(return_value=new_rent_pf)
        existing_pf = _make_periodic_flow(id=FLOW_ID_1)
        periodic_flow_port.get_by_id = AsyncMock(return_value=existing_pf)

        update_payload = _base_re_payload(
            id=str(re_id),
            basic_info={
                "name": "Updated House",
                "is_residence": True,
                "is_rented": True,
            },
            flows=[
                _loan_flow_payload(pf_id=FLOW_ID_1),
                _rent_flow_payload(),
            ],
        )
        update_resp = await _update_re_json(client, update_payload)
        assert update_resp.status_code == 204

        updated = real_estate_port.update.await_args[0][0]
        updated.created_at = datetime(2020, 1, 15, 10, 0, 0)

        # --- LIST after update ---
        real_estate_port.get_all = AsyncMock(return_value=[updated])
        list_resp2 = await client.get(LIST_URL)
        data2 = await list_resp2.get_json()
        assert len(data2) == 1
        assert data2[0]["basic_info"]["name"] == "Updated House"
        assert len(data2[0]["flows"]) == 2

        # --- DELETE ---
        real_estate_port.get_by_id = AsyncMock(return_value=updated)
        del_resp = await client.delete(
            f"{DELETE_URL}/{re_id}", json={"remove_related_flows": True}
        )
        assert del_resp.status_code == 204
        real_estate_port.delete.assert_awaited_once()

        # --- LIST after delete ---
        real_estate_port.get_all = AsyncMock(return_value=[])
        list_resp3 = await client.get(LIST_URL)
        data3 = await list_resp3.get_json()
        assert data3 == []

    @pytest.mark.asyncio
    async def test_lifecycle_photo_and_linked_loan(
        self,
        client,
        real_estate_port,
        periodic_flow_port,
        file_storage_port,
        position_port,
    ):
        # --- CREATE with photo + linked loan ---
        _setup_pf_save(periodic_flow_port, [FLOW_ID_1])
        file_storage_port.save = AsyncMock(return_value="real_estate/house.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/house.jpg"
        )

        payload = _base_re_payload(flows=[_loan_flow_payload(linked_loan_hash="lhash")])
        response = await _create_re(client, payload, photo_bytes=b"photo-data")
        assert response.status_code == 201
        file_storage_port.save.assert_awaited_once()

        inserted = real_estate_port.insert.await_args[0][0]
        inserted.id = uuid.uuid4()
        inserted.created_at = datetime(2020, 1, 15, 10, 0, 0)
        assert inserted.basic_info.photo_url == "/static/real_estate/house.jpg"

        # --- LIST with linked loan injection ---
        real_estate_port.get_all = AsyncMock(return_value=[inserted])
        position_port.get_loans_by_hash = AsyncMock(
            return_value={"lhash": _make_loan("lhash")}
        )
        list_resp = await client.get(LIST_URL)
        data = await list_resp.get_json()
        assert data[0]["basic_info"]["photo_url"] == "/static/real_estate/house.jpg"
        assert data[0]["flows"][0]["payload"]["loan_amount"] == 250000

        # --- UPDATE with new photo ---
        real_estate_port.get_by_id = AsyncMock(return_value=inserted)
        file_storage_port.save = AsyncMock(return_value="real_estate/house2.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/house2.jpg"
        )
        existing_pf = _make_periodic_flow(id=FLOW_ID_1)
        periodic_flow_port.get_by_id = AsyncMock(return_value=existing_pf)

        up_payload = _base_re_payload(
            id=str(inserted.id),
            flows=[_loan_flow_payload(linked_loan_hash="lhash", pf_id=FLOW_ID_1)],
        )
        up_resp = await _update_re_multipart(
            client, up_payload, photo_bytes=b"new-photo"
        )
        assert up_resp.status_code == 204
        updated = real_estate_port.update.await_args[0][0]
        assert updated.basic_info.photo_url == "/static/real_estate/house2.jpg"

        # --- DELETE with cleanup ---
        updated.created_at = datetime(2020, 1, 15, 10, 0, 0)
        real_estate_port.get_by_id = AsyncMock(return_value=updated)
        del_resp = await client.delete(
            f"{DELETE_URL}/{inserted.id}",
            json={"remove_related_flows": True},
        )
        assert del_resp.status_code == 204
        file_storage_port.delete_by_url.assert_awaited()
        periodic_flow_port.delete.assert_awaited()


# =========================================================================
# CREATE PHOTO ROLLBACK
# =========================================================================


class TestCreatePhotoRollback:
    @pytest.mark.asyncio
    async def test_photo_rollback_on_insert_failure(
        self, client, real_estate_port, file_storage_port
    ):
        file_storage_port.save = AsyncMock(return_value="real_estate/tmp.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/tmp.jpg"
        )
        real_estate_port.insert = AsyncMock(side_effect=RuntimeError("DB error"))

        response = await _create_re(client, _base_re_payload(), photo_bytes=b"img")
        assert response.status_code == 500
        file_storage_port.delete_by_url.assert_awaited_once_with(
            "/static/real_estate/tmp.jpg"
        )
