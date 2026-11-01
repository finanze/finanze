from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from application.ports.label_port import LabelPort
from application.ports.periodic_flow_port import PeriodicFlowPort
from application.use_cases.save_periodic_flow import SavePeriodicFlowImpl
from application.use_cases.update_periodic_flow import UpdatePeriodicFlowImpl
from domain.dezimal import Dezimal
from domain.earnings_expenses import (
    FlowFrequency,
    FlowType,
    PeriodicFlow,
    RealEstateFlowInfo,
)
from domain.exception.exceptions import InvalidBudgetLabel, LabelNotFound
from domain.labeling import Label, LabelCategory


def _flow(**overrides):
    return PeriodicFlow(
        **{
            "id": uuid4(),
            "name": "Groceries",
            "amount": Dezimal("600"),
            "currency": "EUR",
            "flow_type": FlowType.EXPENSE,
            "frequency": FlowFrequency.MONTHLY,
            "category": "Household",
            "enabled": True,
            "since": date(2025, 1, 1),
            "until": None,
            "icon": None,
            **overrides,
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("use_case", [SavePeriodicFlowImpl, UpdatePeriodicFlowImpl])
async def test_label_is_validated_before_persistence(use_case):
    port = AsyncMock(spec=PeriodicFlowPort)
    port.get_by_id.return_value = None
    labels = AsyncMock(spec=LabelPort)
    flow = _flow(label_id=uuid4())
    labels.get_by_id.return_value = Label(id=flow.label_id)
    await use_case(port, labels).execute(flow)
    labels.get_by_id.assert_awaited_once_with(flow.label_id)
    method = port.save if use_case is SavePeriodicFlowImpl else port.update
    method.assert_awaited_once_with(flow)


@pytest.mark.asyncio
@pytest.mark.parametrize("use_case", [SavePeriodicFlowImpl, UpdatePeriodicFlowImpl])
@pytest.mark.parametrize("excluded", [False, True])
async def test_invalid_label_does_not_write(use_case, excluded):
    port = AsyncMock(spec=PeriodicFlowPort)
    port.get_by_id.return_value = None
    labels = AsyncMock(spec=LabelPort)
    flow = _flow(label_id=uuid4())
    labels.get_by_id.return_value = (
        Label(id=flow.label_id, category=LabelCategory.EXCLUDED) if excluded else None
    )
    with pytest.raises(InvalidBudgetLabel if excluded else LabelNotFound):
        await use_case(port, labels).execute(flow)
    port.save.assert_not_awaited()
    port.update.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("use_case", [SavePeriodicFlowImpl, UpdatePeriodicFlowImpl])
async def test_unassigned_budget_avoids_label_lookup(use_case):
    port = AsyncMock(spec=PeriodicFlowPort)
    port.get_by_id.return_value = None
    labels = AsyncMock(spec=LabelPort)
    await use_case(port, labels).execute(_flow())
    labels.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_omitted_label_preserves_reference_without_extra_lookup():
    port = AsyncMock(spec=PeriodicFlowPort)
    original = _flow(label_id=uuid4())
    port.get_by_id.return_value = original
    labels = AsyncMock(spec=LabelPort)
    flow = _flow(id=original.id)
    await UpdatePeriodicFlowImpl(port, labels).execute(flow, label_id_provided=False)
    assert flow.label_id == original.label_id
    labels.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_loan_label_is_editable_but_managed_amount_is_preserved():
    port = AsyncMock(spec=PeriodicFlowPort)
    original = _flow(real_estate_flow=RealEstateFlowInfo(flow_subtype="LOAN"))
    port.get_by_id.return_value = original
    labels = AsyncMock(spec=LabelPort)
    flow = _flow(id=original.id, amount=Dezimal("999"), label_id=uuid4())
    labels.get_by_id.return_value = Label(id=flow.label_id)
    await UpdatePeriodicFlowImpl(port, labels).execute(flow)
    assert flow.amount == original.amount
    assert flow.label_id is not None
    port.update.assert_awaited_once_with(flow)
