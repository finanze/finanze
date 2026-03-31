import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from application.ports.file_storage_port import FileStoragePort
from application.ports.periodic_flow_port import PeriodicFlowPort
from application.ports.real_estate_port import RealEstatePort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.create_real_estate import CreateRealEstateImpl
from application.use_cases.update_real_estate import UpdateRealEstateImpl
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.exception.exceptions import FlowNotFound, RealEstateNotFound
from domain.global_position import InterestType, LoanType
from domain.real_estate import (
    BasicInfo,
    CostPayload,
    CreateRealEstateRequest,
    Location,
    LoanPayload,
    PurchaseInfo,
    RealEstate,
    RealEstateFlow,
    RealEstateFlowSubtype,
    RentPayload,
    SupplyPayload,
    UpdateRealEstateRequest,
    ValuationInfo,
)


def _mock_transaction_handler():
    transaction_handler_port = MagicMock(spec=TransactionHandlerPort)
    transaction_ctx = MagicMock()
    transaction_ctx.__aenter__ = AsyncMock(return_value=None)
    transaction_ctx.__aexit__ = AsyncMock(return_value=None)
    transaction_handler_port.start = MagicMock(return_value=transaction_ctx)
    return transaction_handler_port


def _make_pf(id=None, name="Mortgage", amount=Dezimal(500)):
    return PeriodicFlow(
        id=id,
        name=name,
        amount=amount,
        currency="EUR",
        flow_type=FlowType.EXPENSE,
        frequency=FlowFrequency.MONTHLY,
        category="housing",
        enabled=True,
        since=date(2020, 1, 1),
        until=None,
        icon=None,
    )


def _make_re(id=None, flows=None):
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


class TestCreateRealEstateWithLinkedLoan:
    def _build(self):
        real_estate_port = AsyncMock(spec=RealEstatePort)
        periodic_flow_port = AsyncMock(spec=PeriodicFlowPort)
        file_storage_port = AsyncMock(spec=FileStoragePort)
        file_storage_port.get_url = MagicMock(
            return_value="http://example.com/photo.jpg"
        )
        transaction_handler_port = _mock_transaction_handler()

        uc = CreateRealEstateImpl(
            real_estate_port,
            periodic_flow_port,
            transaction_handler_port,
            file_storage_port,
        )
        return uc, real_estate_port, periodic_flow_port, file_storage_port

    @pytest.mark.asyncio
    async def test_create_with_linked_loan_flow(self):
        """Linked loan has loan_amount=None, linked_loan_hash set."""
        uc, re_port, pf_port, _ = self._build()
        saved_pf = _make_pf(id=uuid4())
        pf_port.save = AsyncMock(return_value=saved_pf)

        loan_payload = LoanPayload(
            type=LoanType.MORTGAGE,
            loan_amount=None,
            interest_rate=Dezimal(0),
            euribor_rate=None,
            interest_type=InterestType.FIXED,
            fixed_years=None,
            principal_outstanding=Dezimal(0),
            linked_loan_hash="abc123",
        )
        flow = RealEstateFlow(
            periodic_flow_id=None,
            periodic_flow=_make_pf(id=None),
            flow_subtype=RealEstateFlowSubtype.LOAN,
            description="Linked mortgage",
            payload=loan_payload,
        )
        re = _make_re(flows=[flow])
        request = CreateRealEstateRequest(real_estate=re, photo=None)

        await uc.execute(request)

        pf_port.save.assert_awaited_once()
        re_port.insert.assert_awaited_once()
        inserted = re_port.insert.await_args[0][0]
        assert inserted.flows[0].periodic_flow_id == saved_pf.id
        assert inserted.flows[0].payload.linked_loan_hash == "abc123"
        assert inserted.flows[0].payload.loan_amount is None

    @pytest.mark.asyncio
    async def test_create_with_unlinked_loan_flow(self):
        """Unlinked loan has full payload with loan_amount."""
        uc, re_port, pf_port, _ = self._build()
        saved_pf = _make_pf(id=uuid4())
        pf_port.save = AsyncMock(return_value=saved_pf)

        loan_payload = LoanPayload(
            type=LoanType.MORTGAGE,
            loan_amount=Dezimal(200000),
            interest_rate=Dezimal("0.025"),
            euribor_rate=None,
            interest_type=InterestType.FIXED,
            fixed_years=None,
            principal_outstanding=Dezimal(180000),
        )
        flow = RealEstateFlow(
            periodic_flow_id=None,
            periodic_flow=_make_pf(id=None),
            flow_subtype=RealEstateFlowSubtype.LOAN,
            description="Unlinked mortgage",
            payload=loan_payload,
        )
        re = _make_re(flows=[flow])
        request = CreateRealEstateRequest(real_estate=re, photo=None)

        await uc.execute(request)

        pf_port.save.assert_awaited_once()
        re_port.insert.assert_awaited_once()
        inserted = re_port.insert.await_args[0][0]
        assert inserted.flows[0].payload.loan_amount == Dezimal(200000)
        assert inserted.flows[0].payload.linked_loan_hash is None

    @pytest.mark.asyncio
    async def test_create_with_mixed_flow_types(self):
        """Multiple flows: LOAN + RENT + SUPPLY."""
        uc, re_port, pf_port, _ = self._build()
        saved_ids = [uuid4(), uuid4(), uuid4()]
        call_count = 0

        async def save_side_effect(flow):
            nonlocal call_count
            pf = _make_pf(id=saved_ids[call_count], name=flow.name)
            call_count += 1
            return pf

        pf_port.save = AsyncMock(side_effect=save_side_effect)

        loan_flow = RealEstateFlow(
            periodic_flow_id=None,
            periodic_flow=_make_pf(id=None, name="Mortgage"),
            flow_subtype=RealEstateFlowSubtype.LOAN,
            description="Mortgage payment",
            payload=LoanPayload(
                type=LoanType.MORTGAGE,
                loan_amount=Dezimal(200000),
                interest_rate=Dezimal("0.03"),
                euribor_rate=None,
                interest_type=InterestType.FIXED,
                fixed_years=None,
                principal_outstanding=Dezimal(180000),
            ),
        )
        rent_flow = RealEstateFlow(
            periodic_flow_id=None,
            periodic_flow=_make_pf(id=None, name="Rent Income"),
            flow_subtype=RealEstateFlowSubtype.RENT,
            description="Monthly rent",
            payload=RentPayload(),
        )
        supply_flow = RealEstateFlow(
            periodic_flow_id=None,
            periodic_flow=_make_pf(id=None, name="Electricity"),
            flow_subtype=RealEstateFlowSubtype.SUPPLY,
            description="Electricity bill",
            payload=SupplyPayload(tax_deductible=True),
        )

        re = _make_re(flows=[loan_flow, rent_flow, supply_flow])
        request = CreateRealEstateRequest(real_estate=re, photo=None)

        await uc.execute(request)

        assert pf_port.save.await_count == 3
        re_port.insert.assert_awaited_once()
        inserted = re_port.insert.await_args[0][0]
        assert len(inserted.flows) == 3
        subtypes = {f.flow_subtype for f in inserted.flows}
        assert subtypes == {
            RealEstateFlowSubtype.LOAN,
            RealEstateFlowSubtype.RENT,
            RealEstateFlowSubtype.SUPPLY,
        }

    @pytest.mark.asyncio
    async def test_existing_flow_not_found_raises(self):
        """periodic_flow has id but get_by_id returns None -> FlowNotFound."""
        uc, re_port, pf_port, _ = self._build()
        existing_pf_id = uuid4()
        pf_port.get_by_id = AsyncMock(return_value=None)

        flow = RealEstateFlow(
            periodic_flow_id=existing_pf_id,
            periodic_flow=_make_pf(id=existing_pf_id),
            flow_subtype=RealEstateFlowSubtype.LOAN,
            description="Mortgage",
            payload=LoanPayload(
                type=LoanType.MORTGAGE,
                loan_amount=Dezimal(200000),
                interest_rate=Dezimal("0.03"),
                euribor_rate=None,
                interest_type=InterestType.FIXED,
                fixed_years=None,
                principal_outstanding=Dezimal(180000),
            ),
        )
        re = _make_re(flows=[flow])
        request = CreateRealEstateRequest(real_estate=re, photo=None)

        with pytest.raises(FlowNotFound):
            await uc.execute(request)


class TestUpdateRealEstateLinkedLoans:
    def _build(self):
        real_estate_port = AsyncMock(spec=RealEstatePort)
        periodic_flow_port = AsyncMock(spec=PeriodicFlowPort)
        file_storage_port = AsyncMock(spec=FileStoragePort)
        file_storage_port.get_url = MagicMock(
            return_value="http://example.com/photo.jpg"
        )
        transaction_handler_port = _mock_transaction_handler()

        uc = UpdateRealEstateImpl(
            real_estate_port,
            periodic_flow_port,
            transaction_handler_port,
            file_storage_port,
        )
        return uc, real_estate_port, periodic_flow_port, file_storage_port

    @pytest.mark.asyncio
    async def test_switch_unlinked_to_linked_loan(self):
        """Update changes loan from unlinked (full payload) to linked (stub)."""
        uc, re_port, pf_port, _ = self._build()
        existing_flow_id = uuid4()
        re_id = uuid4()

        existing_re = _make_re(
            id=re_id,
            flows=[
                RealEstateFlow(
                    periodic_flow_id=existing_flow_id,
                    periodic_flow=None,
                    flow_subtype=RealEstateFlowSubtype.LOAN,
                    description="Old mortgage",
                    payload=LoanPayload(
                        type=LoanType.MORTGAGE,
                        loan_amount=Dezimal(200000),
                        interest_rate=Dezimal("0.025"),
                        euribor_rate=None,
                        interest_type=InterestType.FIXED,
                        fixed_years=None,
                        principal_outstanding=Dezimal(180000),
                        linked_loan_hash=None,
                    ),
                )
            ],
        )
        re_port.get_by_id = AsyncMock(return_value=existing_re)

        # Update with linked loan
        updated_pf = _make_pf(id=existing_flow_id)
        pf_port.get_by_id = AsyncMock(return_value=updated_pf)

        new_flow = RealEstateFlow(
            periodic_flow_id=existing_flow_id,
            periodic_flow=updated_pf,
            flow_subtype=RealEstateFlowSubtype.LOAN,
            description="Now linked",
            payload=LoanPayload(
                type=LoanType.MORTGAGE,
                loan_amount=None,
                interest_rate=Dezimal(0),
                euribor_rate=None,
                interest_type=InterestType.FIXED,
                fixed_years=None,
                principal_outstanding=Dezimal(0),
                linked_loan_hash="new_hash_123",
            ),
        )
        new_re = _make_re(id=re_id, flows=[new_flow])
        request = UpdateRealEstateRequest(
            real_estate=new_re, remove_unassigned_flows=False, photo=None
        )
        await uc.execute(request)

        pf_port.update.assert_awaited_once()
        re_port.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_switch_linked_to_unlinked_loan(self):
        """Update changes from linked (stub) to unlinked (full payload)."""
        uc, re_port, pf_port, _ = self._build()
        existing_flow_id = uuid4()
        re_id = uuid4()

        existing_re = _make_re(
            id=re_id,
            flows=[
                RealEstateFlow(
                    periodic_flow_id=existing_flow_id,
                    periodic_flow=None,
                    flow_subtype=RealEstateFlowSubtype.LOAN,
                    description="Linked mortgage",
                    payload=LoanPayload(
                        type=LoanType.MORTGAGE,
                        loan_amount=None,
                        interest_rate=Dezimal(0),
                        euribor_rate=None,
                        interest_type=InterestType.FIXED,
                        fixed_years=None,
                        principal_outstanding=Dezimal(0),
                        linked_loan_hash="old_hash",
                    ),
                )
            ],
        )
        re_port.get_by_id = AsyncMock(return_value=existing_re)

        updated_pf = _make_pf(id=existing_flow_id)
        pf_port.get_by_id = AsyncMock(return_value=updated_pf)

        new_flow = RealEstateFlow(
            periodic_flow_id=existing_flow_id,
            periodic_flow=updated_pf,
            flow_subtype=RealEstateFlowSubtype.LOAN,
            description="Now unlinked",
            payload=LoanPayload(
                type=LoanType.MORTGAGE,
                loan_amount=Dezimal(200000),
                interest_rate=Dezimal("0.03"),
                euribor_rate=None,
                interest_type=InterestType.FIXED,
                fixed_years=None,
                principal_outstanding=Dezimal(180000),
                linked_loan_hash=None,
            ),
        )
        new_re = _make_re(id=re_id, flows=[new_flow])
        request = UpdateRealEstateRequest(
            real_estate=new_re, remove_unassigned_flows=False, photo=None
        )
        await uc.execute(request)

        pf_port.update.assert_awaited_once()
        re_port.update.assert_awaited_once()
        updated = re_port.update.await_args[0][0]
        assert updated.flows[0].payload.loan_amount == Dezimal(200000)
        assert updated.flows[0].payload.linked_loan_hash is None

    @pytest.mark.asyncio
    async def test_remove_unassigned_flows_deletes_missing(self):
        """With remove_unassigned_flows=True, existing flows not in update are deleted."""
        uc, re_port, pf_port, _ = self._build()
        re_id = uuid4()
        kept_flow_id = uuid4()
        removed_flow_id = uuid4()

        existing_re = _make_re(
            id=re_id,
            flows=[
                RealEstateFlow(
                    periodic_flow_id=kept_flow_id,
                    periodic_flow=None,
                    flow_subtype=RealEstateFlowSubtype.LOAN,
                    description="Kept flow",
                    payload=LoanPayload(
                        type=LoanType.MORTGAGE,
                        loan_amount=Dezimal(200000),
                        interest_rate=Dezimal("0.03"),
                        euribor_rate=None,
                        interest_type=InterestType.FIXED,
                        fixed_years=None,
                        principal_outstanding=Dezimal(180000),
                    ),
                ),
                RealEstateFlow(
                    periodic_flow_id=removed_flow_id,
                    periodic_flow=None,
                    flow_subtype=RealEstateFlowSubtype.SUPPLY,
                    description="Removed supply",
                    payload=SupplyPayload(tax_deductible=False),
                ),
            ],
        )
        re_port.get_by_id = AsyncMock(return_value=existing_re)

        updated_pf = _make_pf(id=kept_flow_id)
        pf_port.get_by_id = AsyncMock(return_value=updated_pf)

        new_flow = RealEstateFlow(
            periodic_flow_id=kept_flow_id,
            periodic_flow=updated_pf,
            flow_subtype=RealEstateFlowSubtype.LOAN,
            description="Kept flow",
            payload=LoanPayload(
                type=LoanType.MORTGAGE,
                loan_amount=Dezimal(200000),
                interest_rate=Dezimal("0.03"),
                euribor_rate=None,
                interest_type=InterestType.FIXED,
                fixed_years=None,
                principal_outstanding=Dezimal(180000),
            ),
        )
        new_re = _make_re(id=re_id, flows=[new_flow])
        request = UpdateRealEstateRequest(
            real_estate=new_re, remove_unassigned_flows=True, photo=None
        )
        await uc.execute(request)

        pf_port.delete.assert_awaited_once_with(removed_flow_id)

    @pytest.mark.asyncio
    async def test_remove_unassigned_false_keeps_all(self):
        """With remove_unassigned_flows=False, nothing is deleted."""
        uc, re_port, pf_port, _ = self._build()
        re_id = uuid4()
        kept_flow_id = uuid4()
        other_flow_id = uuid4()

        existing_re = _make_re(
            id=re_id,
            flows=[
                RealEstateFlow(
                    periodic_flow_id=kept_flow_id,
                    periodic_flow=None,
                    flow_subtype=RealEstateFlowSubtype.LOAN,
                    description="Kept flow",
                    payload=LoanPayload(
                        type=LoanType.MORTGAGE,
                        loan_amount=Dezimal(200000),
                        interest_rate=Dezimal("0.03"),
                        euribor_rate=None,
                        interest_type=InterestType.FIXED,
                        fixed_years=None,
                        principal_outstanding=Dezimal(180000),
                    ),
                ),
                RealEstateFlow(
                    periodic_flow_id=other_flow_id,
                    periodic_flow=None,
                    flow_subtype=RealEstateFlowSubtype.SUPPLY,
                    description="Other supply",
                    payload=SupplyPayload(tax_deductible=False),
                ),
            ],
        )
        re_port.get_by_id = AsyncMock(return_value=existing_re)

        updated_pf = _make_pf(id=kept_flow_id)
        pf_port.get_by_id = AsyncMock(return_value=updated_pf)

        new_flow = RealEstateFlow(
            periodic_flow_id=kept_flow_id,
            periodic_flow=updated_pf,
            flow_subtype=RealEstateFlowSubtype.LOAN,
            description="Kept flow",
            payload=LoanPayload(
                type=LoanType.MORTGAGE,
                loan_amount=Dezimal(200000),
                interest_rate=Dezimal("0.03"),
                euribor_rate=None,
                interest_type=InterestType.FIXED,
                fixed_years=None,
                principal_outstanding=Dezimal(180000),
            ),
        )
        new_re = _make_re(id=re_id, flows=[new_flow])
        request = UpdateRealEstateRequest(
            real_estate=new_re, remove_unassigned_flows=False, photo=None
        )
        await uc.execute(request)

        pf_port.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_nonexistent_real_estate_raises(self):
        """get_by_id returns None -> RealEstateNotFound."""
        uc, re_port, pf_port, _ = self._build()
        re_port.get_by_id = AsyncMock(return_value=None)

        re = _make_re()
        request = UpdateRealEstateRequest(
            real_estate=re, remove_unassigned_flows=False, photo=None
        )

        with pytest.raises(RealEstateNotFound):
            await uc.execute(request)

    @pytest.mark.asyncio
    async def test_add_new_flow_to_existing_real_estate(self):
        """Adding a new flow (periodic_flow_id=None) saves it."""
        uc, re_port, pf_port, _ = self._build()
        re_id = uuid4()
        new_pf_id = uuid4()

        existing_re = _make_re(id=re_id, flows=[])
        re_port.get_by_id = AsyncMock(return_value=existing_re)

        saved_pf = _make_pf(id=new_pf_id, name="New Cost")
        pf_port.save = AsyncMock(return_value=saved_pf)

        new_flow = RealEstateFlow(
            periodic_flow_id=None,
            periodic_flow=_make_pf(id=None, name="New Cost"),
            flow_subtype=RealEstateFlowSubtype.COST,
            description="New insurance cost",
            payload=CostPayload(tax_deductible=True),
        )
        new_re = _make_re(id=re_id, flows=[new_flow])
        request = UpdateRealEstateRequest(
            real_estate=new_re, remove_unassigned_flows=False, photo=None
        )
        await uc.execute(request)

        pf_port.save.assert_awaited_once()
        re_port.update.assert_awaited_once()
        updated = re_port.update.await_args[0][0]
        assert updated.flows[0].periodic_flow_id == new_pf_id
