from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.ports.file_storage_port import FileStoragePort
from application.ports.periodic_flow_port import PeriodicFlowPort
from application.ports.real_estate_port import RealEstatePort
from application.use_cases.create_real_estate import CreateRealEstateImpl
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.exception.exceptions import FlowNotFound, MarketValueValuationRequired
from domain.global_position import InterestType, LoanType
from domain.real_estate import (
    BasicInfo,
    CreateRealEstateRequest,
    LoanPayload,
    Location,
    PurchaseInfo,
    RealEstate,
    RealEstateFlow,
    RealEstateFlowSubtype,
    RentPayload,
    Valuation,
    ValuationInfo,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_use_case():
    re_port = AsyncMock(spec=RealEstatePort)
    pf_port = AsyncMock(spec=PeriodicFlowPort)
    tx_handler = MagicMock()
    tx_handler.start.return_value = AsyncMock()
    file_port = AsyncMock(spec=FileStoragePort)
    file_port.get_url = MagicMock(return_value="http://example.com/photo.jpg")
    uc = CreateRealEstateImpl(re_port, pf_port, tx_handler, file_port)
    return uc, re_port, pf_port, file_port


def _make_periodic_flow(id=None):
    return PeriodicFlow(
        id=id or uuid4(),
        name="Mortgage",
        amount=Dezimal(500),
        currency="EUR",
        flow_type=FlowType.EXPENSE,
        frequency=FlowFrequency.MONTHLY,
        category="housing",
        enabled=True,
        since=date(2020, 1, 1),
        until=None,
        icon=None,
    )


def _make_flow(
    periodic_flow_id=None, periodic_flow=None, subtype=RealEstateFlowSubtype.LOAN
):
    return RealEstateFlow(
        periodic_flow_id=periodic_flow_id,
        periodic_flow=periodic_flow,
        flow_subtype=subtype,
        description="Test flow",
        payload=LoanPayload(
            type=LoanType.MORTGAGE,
            loan_amount=Dezimal(200000),
            interest_rate=Dezimal("0.025"),
            euribor_rate=None,
            interest_type=InterestType.FIXED,
            fixed_years=None,
            principal_outstanding=Dezimal(180000),
        )
        if subtype == RealEstateFlowSubtype.LOAN
        else RentPayload(),
    )


def _make_real_estate(id=None, flows=None):
    return RealEstate(
        id=id or uuid4(),
        basic_info=BasicInfo(name="Test House", is_residence=True, is_rented=False),
        location=Location(address="123 Main St"),
        purchase_info=PurchaseInfo(
            date=date(2020, 1, 1), price=Dezimal(200000), expenses=[]
        ),
        valuation_info=ValuationInfo(
            estimated_market_value=Dezimal(250000),
            valuations=[
                Valuation(
                    date=date(2020, 1, 1),
                    amount=Dezimal(250000),
                    notes=None,
                    market_value=True,
                )
            ],
        ),
        flows=flows or [],
        currency="EUR",
        rental_data=None,
    )


def _make_request(real_estate, photo=None):
    return CreateRealEstateRequest(real_estate=real_estate, photo=photo)


# ---------------------------------------------------------------------------
# TestCreateRealEstate
# ---------------------------------------------------------------------------


class TestCreateRealEstate:
    @pytest.mark.asyncio
    async def test_create_with_new_flow(self):
        uc, re_port, pf_port, _ = _build_use_case()

        pf = _make_periodic_flow(id=None)
        saved_pf = _make_periodic_flow()
        pf_port.save.return_value = saved_pf

        flow = _make_flow(periodic_flow_id=None, periodic_flow=pf)
        re = _make_real_estate(flows=[flow])
        request = _make_request(re)

        await uc.execute(request)

        pf_port.save.assert_awaited_once_with(pf)
        assert flow.periodic_flow_id == saved_pf.id

    @pytest.mark.asyncio
    async def test_create_with_existing_flow(self):
        uc, re_port, pf_port, _ = _build_use_case()

        pf_id = uuid4()
        pf = _make_periodic_flow(id=pf_id)
        existing_pf = _make_periodic_flow(id=pf_id)
        pf_port.get_by_id.return_value = existing_pf

        flow = _make_flow(periodic_flow_id=pf_id, periodic_flow=pf)
        re = _make_real_estate(flows=[flow])
        request = _make_request(re)

        await uc.execute(request)

        pf_port.get_by_id.assert_awaited_once_with(pf_id)
        pf_port.update.assert_awaited_once_with(pf)
        pf_port.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_with_no_flows(self):
        uc, re_port, pf_port, _ = _build_use_case()

        re = _make_real_estate(flows=[])
        request = _make_request(re)

        await uc.execute(request)

        pf_port.save.assert_not_awaited()
        pf_port.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_existing_flow_not_found_raises(self):
        uc, re_port, pf_port, _ = _build_use_case()

        pf_id = uuid4()
        pf = _make_periodic_flow(id=pf_id)
        pf_port.get_by_id.return_value = None

        flow = _make_flow(periodic_flow_id=pf_id, periodic_flow=pf)
        re = _make_real_estate(flows=[flow])
        request = _make_request(re)

        with pytest.raises(FlowNotFound):
            await uc.execute(request)

        re_port.insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_insert_called(self):
        uc, re_port, pf_port, _ = _build_use_case()

        re = _make_real_estate(flows=[])
        request = _make_request(re)

        await uc.execute(request)

        re_port.insert.assert_awaited_once_with(re)

    @pytest.mark.asyncio
    async def test_no_market_value_valuation_raises(self):
        uc, re_port, _, _ = _build_use_case()

        re = _make_real_estate(flows=[])
        re.valuation_info.valuations = []
        request = _make_request(re)

        with pytest.raises(MarketValueValuationRequired):
            await uc.execute(request)

        re_port.insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_estimated_market_value_derived_from_latest_market_valuation(self):
        uc, re_port, _, _ = _build_use_case()

        re = _make_real_estate(flows=[])
        re.valuation_info.valuations = [
            Valuation(
                date=date(2021, 1, 1),
                amount=Dezimal(260000),
                notes=None,
                market_value=True,
            ),
            Valuation(
                date=date(2023, 6, 1),
                amount=Dezimal(300000),
                notes=None,
                market_value=True,
            ),
            Valuation(
                date=date(2024, 1, 1),
                amount=Dezimal(999999),
                notes=None,
                market_value=False,
            ),
        ]
        request = _make_request(re)

        await uc.execute(request)

        assert re.valuation_info.estimated_market_value == Dezimal(300000)
        re_port.insert.assert_awaited_once_with(re)
