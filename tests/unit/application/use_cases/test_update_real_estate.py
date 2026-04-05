from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.ports.file_storage_port import FileStoragePort
from application.ports.periodic_flow_port import PeriodicFlowPort
from application.ports.real_estate_port import RealEstatePort
from application.use_cases.update_real_estate import UpdateRealEstateImpl
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.exception.exceptions import RealEstateNotFound
from domain.global_position import InterestType, LoanType
from domain.real_estate import (
    BasicInfo,
    LoanPayload,
    Location,
    PurchaseInfo,
    RealEstate,
    RealEstateFlow,
    RealEstateFlowSubtype,
    RentPayload,
    UpdateRealEstateRequest,
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
    uc = UpdateRealEstateImpl(re_port, pf_port, tx_handler, file_port)
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
            estimated_market_value=Dezimal(250000), valuations=[]
        ),
        flows=flows or [],
        currency="EUR",
        rental_data=None,
    )


def _make_existing_re(id=None, flows=None, photo_url=None, currency="EUR"):
    return RealEstate(
        id=id or uuid4(),
        basic_info=BasicInfo(
            name="Test House",
            is_residence=True,
            is_rented=False,
            photo_url=photo_url,
        ),
        location=Location(address="123 Main St"),
        purchase_info=PurchaseInfo(
            date=date(2020, 1, 1), price=Dezimal(200000), expenses=[]
        ),
        valuation_info=ValuationInfo(
            estimated_market_value=Dezimal(250000), valuations=[]
        ),
        flows=flows or [],
        currency=currency,
        rental_data=None,
        created_at=datetime(2020, 1, 15, 10, 0, 0),
        updated_at=datetime(2023, 6, 1, 12, 0, 0),
    )


def _make_request(real_estate, remove_unassigned_flows=True, photo=None):
    return UpdateRealEstateRequest(
        real_estate=real_estate,
        remove_unassigned_flows=remove_unassigned_flows,
        photo=photo,
    )


# ---------------------------------------------------------------------------
# TestUpdateRealEstate
# ---------------------------------------------------------------------------


class TestUpdateRealEstate:
    @pytest.mark.asyncio
    async def test_nonexistent_real_estate_raises(self):
        uc, re_port, pf_port, _ = _build_use_case()

        re_port.get_by_id.return_value = None

        re = _make_real_estate()
        request = _make_request(re)

        with pytest.raises(RealEstateNotFound):
            await uc.execute(request)

        re_port.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_add_new_flow(self):
        uc, re_port, pf_port, _ = _build_use_case()

        re_id = uuid4()
        existing_re = _make_existing_re(id=re_id, flows=[])
        re_port.get_by_id.return_value = existing_re

        new_pf = _make_periodic_flow(id=None)
        saved_pf = _make_periodic_flow()
        pf_port.save.return_value = saved_pf

        flow = _make_flow(periodic_flow_id=None, periodic_flow=new_pf)
        update_re = _make_real_estate(id=re_id, flows=[flow])
        request = _make_request(update_re, remove_unassigned_flows=False)

        await uc.execute(request)

        pf_port.save.assert_awaited_once_with(new_pf)
        assert flow.periodic_flow_id == saved_pf.id

    @pytest.mark.asyncio
    async def test_remove_unassigned_flow(self):
        uc, re_port, pf_port, _ = _build_use_case()

        re_id = uuid4()
        old_pf_id = uuid4()

        existing_flow = _make_flow(
            periodic_flow_id=old_pf_id, subtype=RealEstateFlowSubtype.RENT
        )
        existing_re = _make_existing_re(id=re_id, flows=[existing_flow])
        re_port.get_by_id.return_value = existing_re

        update_re = _make_real_estate(id=re_id, flows=[])
        request = _make_request(update_re, remove_unassigned_flows=True)

        await uc.execute(request)

        pf_port.delete.assert_awaited_once_with(old_pf_id)

    @pytest.mark.asyncio
    async def test_remove_unassigned_false_keeps_all(self):
        uc, re_port, pf_port, _ = _build_use_case()

        re_id = uuid4()
        old_pf_id = uuid4()

        existing_flow = _make_flow(
            periodic_flow_id=old_pf_id, subtype=RealEstateFlowSubtype.RENT
        )
        existing_re = _make_existing_re(id=re_id, flows=[existing_flow])
        re_port.get_by_id.return_value = existing_re

        update_re = _make_real_estate(id=re_id, flows=[])
        request = _make_request(update_re, remove_unassigned_flows=False)

        await uc.execute(request)

        pf_port.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_existing_flow(self):
        uc, re_port, pf_port, _ = _build_use_case()

        re_id = uuid4()
        pf_id = uuid4()

        existing_flow = _make_flow(
            periodic_flow_id=pf_id, subtype=RealEstateFlowSubtype.RENT
        )
        existing_re = _make_existing_re(id=re_id, flows=[existing_flow])
        re_port.get_by_id.return_value = existing_re

        updated_pf = _make_periodic_flow(id=pf_id)
        pf_port.get_by_id.return_value = _make_periodic_flow(id=pf_id)

        flow = _make_flow(
            periodic_flow_id=pf_id,
            periodic_flow=updated_pf,
            subtype=RealEstateFlowSubtype.RENT,
        )
        update_re = _make_real_estate(id=re_id, flows=[flow])
        request = _make_request(update_re, remove_unassigned_flows=False)

        await uc.execute(request)

        pf_port.get_by_id.assert_awaited_with(pf_id)
        pf_port.update.assert_awaited_once_with(updated_pf)
        pf_port.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_preserves_existing_photo_url(self):
        uc, re_port, pf_port, _ = _build_use_case()

        re_id = uuid4()
        existing_photo = "http://example.com/old_photo.jpg"
        existing_re = _make_existing_re(id=re_id, photo_url=existing_photo)
        re_port.get_by_id.return_value = existing_re

        update_re = _make_real_estate(id=re_id)
        request = _make_request(update_re, photo=None)

        await uc.execute(request)

        assert update_re.basic_info.photo_url == existing_photo

    @pytest.mark.asyncio
    async def test_preserves_existing_currency(self):
        uc, re_port, pf_port, _ = _build_use_case()

        re_id = uuid4()
        existing_re = _make_existing_re(id=re_id, currency="USD")
        re_port.get_by_id.return_value = existing_re

        update_re = _make_real_estate(id=re_id)
        request = _make_request(update_re)

        await uc.execute(request)

        assert update_re.currency == "USD"
