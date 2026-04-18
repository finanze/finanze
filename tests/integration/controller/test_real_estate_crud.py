import io
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from werkzeug.datastructures import FileStorage

from domain.dezimal import Dezimal
from domain.global_position import (
    InstallmentFrequency,
    InterestType,
    Loan,
    LoanType,
)
from domain.fetch_record import DataSource

CREATE_URL = "/api/v1/real-estate"
UPDATE_URL = "/api/v1/real-estate"
LIST_URL = "/api/v1/real-estate"
DELETE_URL = "/api/v1/real-estate"
SIGNUP_URL = "/api/v1/signup"
FLOWS_URL = "/api/v1/flows/periodic"

USERNAME = "testuser"
PASSWORD = "securePass123"


async def _signup(client):
    response = await client.post(
        SIGNUP_URL, json={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 204


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
        flow["linked_loan_hash"] = linked_loan_hash
        flow["payload"] = {}
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


async def _list_re(client):
    resp = await client.get(LIST_URL)
    assert resp.status_code == 200
    return await resp.get_json()


def _make_loan(hash_val="hash1"):
    return Loan(
        id=uuid.uuid4(),
        type=LoanType.MORTGAGE,
        currency="EUR",
        current_installment=Dezimal(800),
        interest_rate=Dezimal("0.025"),
        loan_amount=Dezimal(250000),
        creation="2020-01-01",
        maturity="2050-01-01",
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
        payload = {"basic_info": {}}
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


class TestCreateBasic:
    @pytest.mark.asyncio
    async def test_create_minimal_no_flows_no_photo(self, client, file_storage_port):
        await _signup(client)
        response = await _create_re(client, _base_re_payload())
        assert response.status_code == 201
        file_storage_port.save.assert_not_awaited()

        data = await _list_re(client)
        assert len(data) == 1
        assert data[0]["basic_info"]["name"] == "Test House"
        assert data[0]["flows"] == []

    @pytest.mark.asyncio
    async def test_create_with_photo_upload(self, client, file_storage_port):
        await _signup(client)
        file_storage_port.save = AsyncMock(return_value="real_estate/abc.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/abc.jpg"
        )

        response = await _create_re(client, _base_re_payload(), photo_bytes=b"fake-img")
        assert response.status_code == 201
        file_storage_port.save.assert_awaited_once()

        data = await _list_re(client)
        assert data[0]["basic_info"]["photo_url"] == "/static/real_estate/abc.jpg"

    @pytest.mark.asyncio
    async def test_create_with_all_optional_fields(self, client):
        await _signup(client)
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

        data = await _list_re(client)
        item = data[0]
        assert item["basic_info"]["bathrooms"] == 3
        assert item["basic_info"]["bedrooms"] == 5
        assert item["location"]["cadastral_reference"] == "CAD-123"
        assert len(item["purchase_info"]["expenses"]) == 1
        assert len(item["valuation_info"]["valuations"]) == 1
        assert item["rental_data"] is not None
        assert len(item["rental_data"]["amortizations"]) == 1


class TestCreateWithFlows:
    @pytest.mark.asyncio
    async def test_create_single_unlinked_loan(self, client):
        await _signup(client)
        payload = _base_re_payload(flows=[_loan_flow_payload()])
        response = await _create_re(client, payload)
        assert response.status_code == 201

        data = await _list_re(client)
        assert len(data[0]["flows"]) == 1
        flow = data[0]["flows"][0]
        assert flow["flow_subtype"] == "LOAN"
        assert flow["payload"]["loan_amount"] == 200000
        assert flow["linked_loan_hash"] is None
        assert flow["periodic_flow"]["name"] == "Mortgage Payment"

    @pytest.mark.asyncio
    async def test_create_single_linked_loan(self, client, position_port):
        await _signup(client)
        payload = _base_re_payload(flows=[_loan_flow_payload(linked_loan_hash="hash1")])
        response = await _create_re(client, payload)
        assert response.status_code == 201

        position_port.get_loans_by_hash = AsyncMock(
            return_value={"hash1": _make_loan("hash1")}
        )

        data = await _list_re(client)
        flow = data[0]["flows"][0]
        assert flow["linked_loan_hash"] == "hash1"
        assert flow["payload"]["loan_amount"] == 250000
        assert flow["payload"]["interest_rate"] == pytest.approx(0.025)

    @pytest.mark.asyncio
    async def test_create_rent_flow(self, client):
        await _signup(client)
        payload = _base_re_payload(flows=[_rent_flow_payload()])
        response = await _create_re(client, payload)
        assert response.status_code == 201

        data = await _list_re(client)
        flow = data[0]["flows"][0]
        assert flow["flow_subtype"] == "RENT"

    @pytest.mark.asyncio
    async def test_create_supply_flow(self, client):
        await _signup(client)
        payload = _base_re_payload(flows=[_supply_flow_payload(tax_deductible=True)])
        response = await _create_re(client, payload)
        assert response.status_code == 201

        data = await _list_re(client)
        flow = data[0]["flows"][0]
        assert flow["flow_subtype"] == "SUPPLY"
        assert flow["payload"]["tax_deductible"] is True

    @pytest.mark.asyncio
    async def test_create_cost_flow(self, client):
        await _signup(client)
        payload = _base_re_payload(flows=[_cost_flow_payload(tax_deductible=False)])
        response = await _create_re(client, payload)
        assert response.status_code == 201

        data = await _list_re(client)
        flow = data[0]["flows"][0]
        assert flow["flow_subtype"] == "COST"
        assert flow["payload"]["tax_deductible"] is False

    @pytest.mark.asyncio
    async def test_create_mixed_flows(self, client):
        await _signup(client)
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

        data = await _list_re(client)
        subtypes = {f["flow_subtype"] for f in data[0]["flows"]}
        assert subtypes == {"LOAN", "RENT", "SUPPLY", "COST"}


class TestCreateWithExistingFlows:
    @pytest.mark.asyncio
    async def test_existing_flow_updates_it(self, client):
        await _signup(client)
        pf_resp = await client.post(
            FLOWS_URL,
            json=_periodic_flow_dict(name="Original Flow", amount="300"),
        )
        assert pf_resp.status_code == 201

        flows_resp = await client.get(FLOWS_URL)
        flows_data = await flows_resp.get_json()
        pf_id = flows_data[0]["id"]

        payload = _base_re_payload(flows=[_loan_flow_payload(pf_id=pf_id)])
        response = await _create_re(client, payload)
        assert response.status_code == 201

        data = await _list_re(client)
        assert len(data[0]["flows"]) == 1
        assert data[0]["flows"][0]["periodic_flow"]["name"] == "Mortgage Payment"

    @pytest.mark.asyncio
    async def test_existing_flow_not_found_returns_400(self, client):
        await _signup(client)
        fake_id = str(uuid.uuid4())
        payload = _base_re_payload(flows=[_loan_flow_payload(pf_id=fake_id)])
        response = await _create_re(client, payload)
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"


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
    async def test_update_nonexistent_re_returns_404(self, client):
        await _signup(client)
        payload = _base_re_payload(id=str(uuid.uuid4()))
        response = await _update_re_json(client, payload)
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "NOT_FOUND"


class TestUpdateBasic:
    @pytest.mark.asyncio
    async def test_update_via_json(self, client):
        await _signup(client)
        await _create_re(client, _base_re_payload())
        data = await _list_re(client)
        re_id = data[0]["id"]

        payload = _base_re_payload(
            id=re_id,
            basic_info={
                "name": "Updated House",
                "is_residence": False,
                "is_rented": True,
            },
        )
        response = await _update_re_json(client, payload)
        assert response.status_code == 204

        data = await _list_re(client)
        assert data[0]["basic_info"]["name"] == "Updated House"
        assert data[0]["basic_info"]["is_rented"] is True

    @pytest.mark.asyncio
    async def test_update_via_multipart(self, client):
        await _signup(client)
        await _create_re(client, _base_re_payload())
        data = await _list_re(client)
        re_id = data[0]["id"]

        payload = _base_re_payload(id=re_id)
        response = await _update_re_multipart(client, payload)
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_update_preserves_currency(self, client):
        await _signup(client)
        await _create_re(client, _base_re_payload(currency="EUR"))
        data = await _list_re(client)
        re_id = data[0]["id"]

        payload = _base_re_payload(id=re_id, currency="USD")
        await _update_re_json(client, payload)

        data = await _list_re(client)
        assert data[0]["currency"] == "EUR"

    @pytest.mark.asyncio
    async def test_update_preserves_photo_when_no_upload(
        self, client, file_storage_port
    ):
        await _signup(client)
        file_storage_port.save = AsyncMock(return_value="real_estate/old.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/old.jpg"
        )
        await _create_re(client, _base_re_payload(), photo_bytes=b"img")
        data = await _list_re(client)
        re_id = data[0]["id"]

        payload = _base_re_payload(id=re_id)
        await _update_re_json(client, payload)

        data = await _list_re(client)
        assert data[0]["basic_info"]["photo_url"] == "/static/real_estate/old.jpg"


class TestUpdatePhotoHandling:
    @pytest.mark.asyncio
    async def test_update_replaces_photo(self, client, file_storage_port):
        await _signup(client)
        file_storage_port.save = AsyncMock(return_value="real_estate/old.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/old.jpg"
        )
        await _create_re(client, _base_re_payload(), photo_bytes=b"old-img")
        data = await _list_re(client)
        re_id = data[0]["id"]

        file_storage_port.save = AsyncMock(return_value="real_estate/new.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/new.jpg"
        )
        payload = _base_re_payload(id=re_id)
        response = await _update_re_multipart(client, payload, photo_bytes=b"new-img")
        assert response.status_code == 204
        file_storage_port.save.assert_awaited_once()
        call_kwargs = file_storage_port.save.await_args
        assert call_kwargs.kwargs.get("existing_url") == "/static/real_estate/old.jpg"

    @pytest.mark.asyncio
    async def test_update_adds_photo_to_re_without_photo(
        self, client, file_storage_port
    ):
        await _signup(client)
        await _create_re(client, _base_re_payload())
        data = await _list_re(client)
        re_id = data[0]["id"]

        file_storage_port.save = AsyncMock(return_value="real_estate/first.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/first.jpg"
        )
        payload = _base_re_payload(id=re_id)
        response = await _update_re_multipart(client, payload, photo_bytes=b"img")
        assert response.status_code == 204

        data = await _list_re(client)
        assert data[0]["basic_info"]["photo_url"] == "/static/real_estate/first.jpg"


class TestUpdateFlows:
    @pytest.mark.asyncio
    async def test_update_adds_new_flow(self, client):
        await _signup(client)
        await _create_re(client, _base_re_payload())
        data = await _list_re(client)
        re_id = data[0]["id"]

        payload = _base_re_payload(id=re_id, flows=[_rent_flow_payload()])
        response = await _update_re_json(client, payload)
        assert response.status_code == 204

        data = await _list_re(client)
        assert len(data[0]["flows"]) == 1
        assert data[0]["flows"][0]["flow_subtype"] == "RENT"

    @pytest.mark.asyncio
    async def test_update_removes_unassigned_flow_when_true(self, client):
        await _signup(client)
        payload = _base_re_payload(flows=[_rent_flow_payload(), _supply_flow_payload()])
        await _create_re(client, payload)
        data = await _list_re(client)
        re_id = data[0]["id"]
        rent_flow = next(f for f in data[0]["flows"] if f["flow_subtype"] == "RENT")
        rent_pf_id = rent_flow["periodic_flow_id"]

        payload = _base_re_payload(
            id=re_id,
            remove_unassigned_flows=True,
            flows=[_rent_flow_payload(pf_id=rent_pf_id)],
        )
        response = await _update_re_json(client, payload)
        assert response.status_code == 204

        data = await _list_re(client)
        assert len(data[0]["flows"]) == 1
        assert data[0]["flows"][0]["flow_subtype"] == "RENT"

        flows_resp = await client.get(FLOWS_URL)
        flows_data = await flows_resp.get_json()
        flow_ids = {f["id"] for f in flows_data}
        assert rent_pf_id in flow_ids

    @pytest.mark.asyncio
    async def test_update_keeps_unassigned_flow_when_false(self, client):
        await _signup(client)
        payload = _base_re_payload(flows=[_rent_flow_payload(), _supply_flow_payload()])
        await _create_re(client, payload)
        data = await _list_re(client)
        re_id = data[0]["id"]
        rent_flow = next(f for f in data[0]["flows"] if f["flow_subtype"] == "RENT")
        rent_pf_id = rent_flow["periodic_flow_id"]

        payload = _base_re_payload(
            id=re_id,
            remove_unassigned_flows=False,
            flows=[_rent_flow_payload(pf_id=rent_pf_id)],
        )
        response = await _update_re_json(client, payload)
        assert response.status_code == 204

        flows_resp = await client.get(FLOWS_URL)
        flows_data = await flows_resp.get_json()
        assert len(flows_data) == 2

    @pytest.mark.asyncio
    async def test_update_loan_unlinked_to_linked(self, client, position_port):
        await _signup(client)
        payload = _base_re_payload(flows=[_loan_flow_payload()])
        await _create_re(client, payload)
        data = await _list_re(client)
        re_id = data[0]["id"]
        pf_id = data[0]["flows"][0]["periodic_flow_id"]

        payload = _base_re_payload(
            id=re_id,
            flows=[_loan_flow_payload(linked_loan_hash="link1", pf_id=pf_id)],
        )
        response = await _update_re_json(client, payload)
        assert response.status_code == 204

        position_port.get_loans_by_hash = AsyncMock(
            return_value={"link1": _make_loan("link1")}
        )
        data = await _list_re(client)
        flow = data[0]["flows"][0]
        assert flow["linked_loan_hash"] == "link1"
        assert flow["payload"]["loan_amount"] == 250000

    @pytest.mark.asyncio
    async def test_update_loan_linked_to_unlinked(self, client, position_port):
        await _signup(client)
        position_port.get_loans_by_hash = AsyncMock(return_value={})
        payload = _base_re_payload(flows=[_loan_flow_payload(linked_loan_hash="link1")])
        await _create_re(client, payload)
        data = await _list_re(client)
        re_id = data[0]["id"]
        pf_id = data[0]["flows"][0]["periodic_flow_id"]

        payload = _base_re_payload(
            id=re_id,
            flows=[_loan_flow_payload(pf_id=pf_id)],
        )
        response = await _update_re_json(client, payload)
        assert response.status_code == 204

        position_port.get_loans_by_hash = AsyncMock(return_value={})
        data = await _list_re(client)
        flow = data[0]["flows"][0]
        assert flow["linked_loan_hash"] is None
        assert flow["payload"]["loan_amount"] == 200000


class TestUpdateRentalData:
    @pytest.mark.asyncio
    async def test_update_preserves_rental_data_when_omitted(self, client):
        await _signup(client)
        payload = _base_re_payload(
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
        await _create_re(client, payload)
        data = await _list_re(client)
        re_id = data[0]["id"]

        update_payload = _base_re_payload(id=re_id)
        response = await _update_re_json(client, update_payload)
        assert response.status_code == 204

        data = await _list_re(client)
        assert data[0]["rental_data"] is not None
        assert data[0]["rental_data"]["marginal_tax_rate"] == 24

    @pytest.mark.asyncio
    async def test_update_replaces_rental_data_when_sent(self, client):
        await _signup(client)
        await _create_re(client, _base_re_payload())
        data = await _list_re(client)
        re_id = data[0]["id"]

        update_payload = _base_re_payload(
            id=re_id,
            rental_data={
                "marginal_tax_rate": 30,
                "vacancy_rate": 10,
                "amortizations": [],
            },
        )
        response = await _update_re_json(client, update_payload)
        assert response.status_code == 204

        data = await _list_re(client)
        assert data[0]["rental_data"] is not None
        assert data[0]["rental_data"]["marginal_tax_rate"] == 30


class TestDeleteValidation:
    @pytest.mark.asyncio
    async def test_delete_invalid_uuid_returns_400(self, client):
        response = await client.delete(f"{DELETE_URL}/not-a-uuid")
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client):
        await _signup(client)
        response = await client.delete(f"{DELETE_URL}/{uuid.uuid4()}")
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "NOT_FOUND"


class TestDeleteBasic:
    @pytest.mark.asyncio
    async def test_delete_no_flows_no_photo(self, client, file_storage_port):
        await _signup(client)
        await _create_re(client, _base_re_payload())
        data = await _list_re(client)
        re_id = data[0]["id"]

        response = await client.delete(f"{DELETE_URL}/{re_id}")
        assert response.status_code == 204
        file_storage_port.delete_by_url.assert_not_awaited()

        data = await _list_re(client)
        assert data == []

    @pytest.mark.asyncio
    async def test_delete_with_photo_cleans_up(self, client, file_storage_port):
        await _signup(client)
        file_storage_port.save = AsyncMock(return_value="real_estate/pic.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/pic.jpg"
        )
        await _create_re(client, _base_re_payload(), photo_bytes=b"img")
        data = await _list_re(client)
        re_id = data[0]["id"]

        response = await client.delete(f"{DELETE_URL}/{re_id}")
        assert response.status_code == 204
        file_storage_port.delete_by_url.assert_awaited_once_with(
            "/static/real_estate/pic.jpg"
        )

    @pytest.mark.asyncio
    async def test_delete_remove_related_flows_true(self, client):
        await _signup(client)
        payload = _base_re_payload(flows=[_loan_flow_payload(), _rent_flow_payload()])
        await _create_re(client, payload)
        data = await _list_re(client)
        re_id = data[0]["id"]

        response = await client.delete(
            f"{DELETE_URL}/{re_id}",
            json={"remove_related_flows": True},
        )
        assert response.status_code == 204

        data = await _list_re(client)
        assert data == []

        flows_resp = await client.get(FLOWS_URL)
        flows_data = await flows_resp.get_json()
        assert len(flows_data) == 0

    @pytest.mark.asyncio
    async def test_delete_remove_related_flows_false(self, client):
        await _signup(client)
        payload = _base_re_payload(flows=[_rent_flow_payload()])
        await _create_re(client, payload)
        data = await _list_re(client)
        re_id = data[0]["id"]

        response = await client.delete(f"{DELETE_URL}/{re_id}")
        assert response.status_code == 204

        data = await _list_re(client)
        assert data == []

        flows_resp = await client.get(FLOWS_URL)
        flows_data = await flows_resp.get_json()
        assert len(flows_data) == 1


class TestListBasic:
    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        await _signup(client)
        data = await _list_re(client)
        assert data == []

    @pytest.mark.asyncio
    async def test_list_single_basic_serialization(self, client):
        await _signup(client)
        await _create_re(client, _base_re_payload())
        data = await _list_re(client)
        assert len(data) == 1
        item = data[0]
        assert item["basic_info"]["name"] == "Test House"
        assert item["location"]["address"] == "123 Main St"
        assert item["purchase_info"]["date"] == "2020-01-15"
        assert item["currency"] == "EUR"
        assert item["created_at"] is not None
        assert item["flows"] == []
        assert item["rental_data"] is None

    @pytest.mark.asyncio
    async def test_list_multiple(self, client):
        await _signup(client)
        await _create_re(
            client,
            _base_re_payload(
                basic_info={
                    "name": "House A",
                    "is_residence": True,
                    "is_rented": False,
                }
            ),
        )
        await _create_re(
            client,
            _base_re_payload(
                basic_info={
                    "name": "House B",
                    "is_residence": False,
                    "is_rented": False,
                }
            ),
        )
        data = await _list_re(client)
        assert len(data) == 2
        names = {d["basic_info"]["name"] for d in data}
        assert names == {"House A", "House B"}

    @pytest.mark.asyncio
    async def test_list_rental_data_serialization(self, client):
        await _signup(client)
        payload = _base_re_payload(
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
        await _create_re(client, payload)
        data = await _list_re(client)
        rd = data[0]["rental_data"]
        assert rd is not None
        assert rd["marginal_tax_rate"] == 24
        assert rd["vacancy_rate"] == 5
        assert len(rd["amortizations"]) == 1
        assert rd["amortizations"][0]["concept"] == "Building"


class TestListLinkedLoanInjection:
    @pytest.mark.asyncio
    async def test_list_injects_linked_loan_data(self, client, position_port):
        await _signup(client)
        payload = _base_re_payload(flows=[_loan_flow_payload(linked_loan_hash="hash1")])
        await _create_re(client, payload)

        loan = _make_loan("hash1")
        position_port.get_loans_by_hash = AsyncMock(return_value={"hash1": loan})

        data = await _list_re(client)
        flow_data = data[0]["flows"][0]
        payload_data = flow_data["payload"]
        assert payload_data["loan_amount"] == 250000
        assert payload_data["principal_outstanding"] == 230000
        assert payload_data["interest_type"] == "VARIABLE"
        assert payload_data["euribor_rate"] == pytest.approx(0.035)
        assert payload_data["monthly_interests"] == 450
        assert flow_data["linked_loan_hash"] == "hash1"

    @pytest.mark.asyncio
    async def test_list_linked_loan_not_found_keeps_stub(self, client, position_port):
        await _signup(client)
        payload = _base_re_payload(
            flows=[_loan_flow_payload(linked_loan_hash="missing_hash")]
        )
        await _create_re(client, payload)

        position_port.get_loans_by_hash = AsyncMock(return_value={})

        data = await _list_re(client)
        flow_data = data[0]["flows"][0]
        payload_data = flow_data["payload"]
        assert payload_data["loan_amount"] is None
        assert flow_data["linked_loan_hash"] == "missing_hash"

    @pytest.mark.asyncio
    async def test_list_mixed_linked_and_unlinked(self, client, position_port):
        await _signup(client)
        payload = _base_re_payload(
            flows=[
                _loan_flow_payload(linked_loan_hash="hash1"),
                _loan_flow_payload(
                    description="Unlinked loan",
                    periodic_flow=_periodic_flow_dict(name="Second Loan", amount="300"),
                ),
            ]
        )
        await _create_re(client, payload)

        loan = _make_loan("hash1")
        position_port.get_loans_by_hash = AsyncMock(return_value={"hash1": loan})

        data = await _list_re(client)
        flows = data[0]["flows"]

        linked = next(f for f in flows if f.get("linked_loan_hash") == "hash1")
        unlinked = next(f for f in flows if not f.get("linked_loan_hash"))

        assert linked["payload"]["loan_amount"] == 250000
        assert unlinked["payload"]["loan_amount"] == 200000


class TestFullCrudLifecycle:
    @pytest.mark.asyncio
    async def test_lifecycle_basic(self, client):
        await _signup(client)

        payload = _base_re_payload(flows=[_loan_flow_payload()])
        response = await _create_re(client, payload)
        assert response.status_code == 201

        data = await _list_re(client)
        assert len(data) == 1
        assert data[0]["basic_info"]["name"] == "Test House"
        assert len(data[0]["flows"]) == 1
        re_id = data[0]["id"]
        pf_id = data[0]["flows"][0]["periodic_flow_id"]

        update_payload = _base_re_payload(
            id=re_id,
            basic_info={
                "name": "Updated House",
                "is_residence": True,
                "is_rented": True,
            },
            flows=[
                _loan_flow_payload(pf_id=pf_id),
                _rent_flow_payload(),
            ],
        )
        update_resp = await _update_re_json(client, update_payload)
        assert update_resp.status_code == 204

        data = await _list_re(client)
        assert len(data) == 1
        assert data[0]["basic_info"]["name"] == "Updated House"
        assert len(data[0]["flows"]) == 2

        del_resp = await client.delete(
            f"{DELETE_URL}/{re_id}", json={"remove_related_flows": True}
        )
        assert del_resp.status_code == 204

        data = await _list_re(client)
        assert data == []

    @pytest.mark.asyncio
    async def test_lifecycle_photo_and_linked_loan(
        self, client, file_storage_port, position_port
    ):
        await _signup(client)

        file_storage_port.save = AsyncMock(return_value="real_estate/house.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/house.jpg"
        )

        payload = _base_re_payload(flows=[_loan_flow_payload(linked_loan_hash="lhash")])
        response = await _create_re(client, payload, photo_bytes=b"photo-data")
        assert response.status_code == 201
        file_storage_port.save.assert_awaited_once()

        position_port.get_loans_by_hash = AsyncMock(
            return_value={"lhash": _make_loan("lhash")}
        )
        data = await _list_re(client)
        assert data[0]["basic_info"]["photo_url"] == "/static/real_estate/house.jpg"
        assert data[0]["flows"][0]["payload"]["loan_amount"] == 250000

        re_id = data[0]["id"]
        pf_id = data[0]["flows"][0]["periodic_flow_id"]

        file_storage_port.save = AsyncMock(return_value="real_estate/house2.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/house2.jpg"
        )
        up_payload = _base_re_payload(
            id=re_id,
            flows=[_loan_flow_payload(linked_loan_hash="lhash", pf_id=pf_id)],
        )
        up_resp = await _update_re_multipart(
            client, up_payload, photo_bytes=b"new-photo"
        )
        assert up_resp.status_code == 204

        data = await _list_re(client)
        assert data[0]["basic_info"]["photo_url"] == "/static/real_estate/house2.jpg"

        del_resp = await client.delete(
            f"{DELETE_URL}/{re_id}",
            json={"remove_related_flows": True},
        )
        assert del_resp.status_code == 204
        file_storage_port.delete_by_url.assert_awaited()

        data = await _list_re(client)
        assert data == []


class TestCreatePhotoRollback:
    @pytest.mark.asyncio
    async def test_photo_rollback_on_insert_failure(
        self, client, file_storage_port, real_estate_port
    ):
        await _signup(client)
        file_storage_port.save = AsyncMock(return_value="real_estate/tmp.jpg")
        file_storage_port.get_url = MagicMock(
            return_value="/static/real_estate/tmp.jpg"
        )

        with patch.object(
            real_estate_port, "insert", side_effect=RuntimeError("DB error")
        ):
            response = await _create_re(client, _base_re_payload(), photo_bytes=b"img")
            assert response.status_code == 500
            file_storage_port.delete_by_url.assert_awaited_once_with(
                "/static/real_estate/tmp.jpg"
            )
