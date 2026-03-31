import pytest

from domain.dezimal import Dezimal
from domain.global_position import InterestType, LoanType
from domain.real_estate import (
    CostPayload,
    LoanPayload,
    RealEstateFlowSubtype,
    RentPayload,
    SupplyPayload,
)
from infrastructure.controller.mappers.real_estate_mapper import (
    _parse_flow_payload,
    map_real_estate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_body(flows=None):
    return {
        "basic_info": {"name": "Test House", "is_residence": True, "is_rented": False},
        "location": {"address": "123 Main St"},
        "purchase_info": {"date": "2020-01-15", "price": "200000", "expenses": []},
        "valuation_info": {"estimated_market_value": "250000", "valuations": []},
        "currency": "EUR",
        "flows": flows or [],
    }


def _make_loan_flow_dict(linked_loan_hash=None):
    payload = {
        "type": "MORTGAGE",
        "interest_rate": "0.03",
        "interest_type": "FIXED",
        "principal_outstanding": "80000",
    }
    if linked_loan_hash:
        payload["linked_loan_hash"] = linked_loan_hash
    else:
        payload["loan_amount"] = "100000"
    return {
        "flow_subtype": "LOAN",
        "payload": payload,
        "description": "Mortgage",
        "periodic_flow": {
            "name": "Mortgage",
            "amount": "500",
            "currency": "EUR",
            "flow_type": "EXPENSE",
            "frequency": "MONTHLY",
            "since": "2020-02-01",
        },
    }


# ---------------------------------------------------------------------------
# TestParseFlowPayloadLoan
# ---------------------------------------------------------------------------


class TestParseFlowPayloadLoan:
    def test_linked_hash_creates_stub(self):
        payload_data = {
            "type": "MORTGAGE",
            "interest_rate": "0.05",
            "interest_type": "VARIABLE",
            "principal_outstanding": "90000",
            "linked_loan_hash": "abc",
        }
        result = _parse_flow_payload(RealEstateFlowSubtype.LOAN, payload_data)

        assert isinstance(result, LoanPayload)
        assert result.loan_amount is None
        assert result.interest_rate == Dezimal(0)
        assert result.linked_loan_hash == "abc"

    def test_no_linked_hash_full_payload(self):
        payload_data = {
            "type": "MORTGAGE",
            "loan_amount": "100000",
            "interest_rate": "0.03",
            "interest_type": "FIXED",
            "principal_outstanding": "80000",
        }
        result = _parse_flow_payload(RealEstateFlowSubtype.LOAN, payload_data)

        assert isinstance(result, LoanPayload)
        assert result.type == LoanType.MORTGAGE
        assert result.loan_amount == Dezimal("100000")
        assert result.interest_rate == Dezimal("0.03")
        assert result.interest_type == InterestType.FIXED
        assert result.principal_outstanding == Dezimal("80000")
        assert result.linked_loan_hash is None

    def test_linked_hash_ignores_other_fields(self):
        payload_data = {
            "type": "STANDARD",
            "interest_rate": "0.05",
            "interest_type": "VARIABLE",
            "principal_outstanding": "90000",
            "loan_amount": "200000",
            "linked_loan_hash": "xyz123",
        }
        result = _parse_flow_payload(RealEstateFlowSubtype.LOAN, payload_data)

        assert result.loan_amount is None
        assert result.interest_rate == Dezimal(0)
        assert result.interest_type == InterestType.FIXED
        assert result.principal_outstanding == Dezimal(0)
        assert result.linked_loan_hash == "xyz123"


# ---------------------------------------------------------------------------
# TestParseFlowPayloadOther
# ---------------------------------------------------------------------------


class TestParseFlowPayloadOther:
    def test_rent_returns_empty(self):
        result = _parse_flow_payload(RealEstateFlowSubtype.RENT, {})
        assert isinstance(result, RentPayload)

    def test_supply_with_tax_deductible(self):
        result = _parse_flow_payload(
            RealEstateFlowSubtype.SUPPLY, {"tax_deductible": True}
        )
        assert isinstance(result, SupplyPayload)
        assert result.tax_deductible is True

    def test_cost_without_tax_deductible(self):
        result = _parse_flow_payload(RealEstateFlowSubtype.COST, {})
        assert isinstance(result, CostPayload)
        assert result.tax_deductible is False

    def test_unknown_subtype_raises(self):
        with pytest.raises(ValueError, match="Unknown flow type"):
            _parse_flow_payload("INVALID_TYPE", {})


# ---------------------------------------------------------------------------
# TestMapRealEstateFlows
# ---------------------------------------------------------------------------


class TestMapRealEstateFlows:
    def test_linked_loan_flow_mapped(self):
        flow_dict = _make_loan_flow_dict(linked_loan_hash="abc")
        body = _make_body(flows=[flow_dict])
        result = map_real_estate(body)

        assert len(result.flows) == 1
        payload = result.flows[0].payload
        assert isinstance(payload, LoanPayload)
        assert payload.linked_loan_hash == "abc"
        assert payload.loan_amount is None
        assert payload.interest_rate == Dezimal(0)

    def test_unlinked_loan_flow_mapped(self):
        flow_dict = _make_loan_flow_dict()
        body = _make_body(flows=[flow_dict])
        result = map_real_estate(body)

        assert len(result.flows) == 1
        payload = result.flows[0].payload
        assert isinstance(payload, LoanPayload)
        assert payload.interest_rate == Dezimal("0.03")
        assert payload.loan_amount == Dezimal("100000")

    def test_mixed_flow_types(self):
        loan_flow = _make_loan_flow_dict()
        rent_flow = {
            "flow_subtype": "RENT",
            "payload": {},
            "description": "Rent income",
            "periodic_flow": {
                "name": "Rent",
                "amount": "800",
                "currency": "EUR",
                "flow_type": "EARNING",
                "frequency": "MONTHLY",
                "since": "2021-01-01",
            },
        }
        supply_flow = {
            "flow_subtype": "SUPPLY",
            "payload": {"tax_deductible": True},
            "description": "Water bill",
            "periodic_flow": {
                "name": "Water",
                "amount": "50",
                "currency": "EUR",
                "flow_type": "EXPENSE",
                "frequency": "MONTHLY",
                "since": "2020-03-01",
            },
        }
        body = _make_body(flows=[loan_flow, rent_flow, supply_flow])
        result = map_real_estate(body)

        assert len(result.flows) == 3
        assert isinstance(result.flows[0].payload, LoanPayload)
        assert isinstance(result.flows[1].payload, RentPayload)
        assert isinstance(result.flows[2].payload, SupplyPayload)

    def test_periodic_flow_id_mismatch_raises(self):
        flow_dict = _make_loan_flow_dict()
        flow_dict["periodic_flow_id"] = "11111111-1111-1111-1111-111111111111"
        flow_dict["periodic_flow"]["id"] = "22222222-2222-2222-2222-222222222222"
        body = _make_body(flows=[flow_dict])

        with pytest.raises(
            ValueError, match="periodic_flow.id and periodic_flow_id not matching"
        ):
            map_real_estate(body)
