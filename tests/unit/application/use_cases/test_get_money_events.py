from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.use_cases.get_money_events import GetMoneyEventsImpl
from domain.dezimal import Dezimal
from domain.earnings_expenses import (
    FlowFrequency,
    FlowType,
    PendingFlow,
    PeriodicFlow,
)
from domain.money_event import MoneyEventQuery, MoneyEventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _periodic_flow(
    name: str = "Test flow",
    amount: Dezimal = Dezimal(100),
    flow_type: FlowType = FlowType.EARNING,
    frequency: FlowFrequency = FlowFrequency.MONTHLY,
    next_date: date | None = date(2025, 4, 10),
    **overrides,
) -> PeriodicFlow:
    defaults = dict(
        id=uuid4(),
        name=name,
        amount=amount,
        currency="EUR",
        flow_type=flow_type,
        frequency=frequency,
        category="general",
        enabled=True,
        since=date(2024, 1, 1),
        until=None,
        icon=None,
        linked=None,
        next_date=next_date,
        max_amount=None,
    )
    defaults.update(overrides)
    return PeriodicFlow(**defaults)


def _pending_flow(
    name: str = "Test pending",
    amount: Dezimal = Dezimal(50),
    flow_type: FlowType = FlowType.EARNING,
    enabled: bool = True,
    flow_date: date | None = date(2025, 4, 15),
    **overrides,
) -> PendingFlow:
    defaults = dict(
        id=uuid4(),
        name=name,
        amount=amount,
        currency="EUR",
        flow_type=flow_type,
        category="general",
        enabled=enabled,
        date=flow_date,
        icon=None,
    )
    defaults.update(overrides)
    return PendingFlow(**defaults)


def _build_use_case(
    periodic_flows: list[PeriodicFlow] | None = None,
    pending_flows: list[PendingFlow] | None = None,
) -> GetMoneyEventsImpl:
    contributions_result = MagicMock()
    contributions_result.contributions = {}

    get_contributions_uc = AsyncMock()
    get_contributions_uc.execute = AsyncMock(return_value=contributions_result)

    get_periodic_flows_uc = AsyncMock()
    get_periodic_flows_uc.execute = AsyncMock(
        return_value=periodic_flows if periodic_flows is not None else []
    )

    get_pending_flows_uc = AsyncMock()
    get_pending_flows_uc.execute = AsyncMock(
        return_value=pending_flows if pending_flows is not None else []
    )

    entity_port = AsyncMock()
    entity_port.get_disabled_entities = AsyncMock(return_value=[])

    position_port = AsyncMock()
    position_port.get_last_grouped_by_entity = AsyncMock(return_value={})

    return GetMoneyEventsImpl(
        get_contributions_uc=get_contributions_uc,
        get_periodic_flows_uc=get_periodic_flows_uc,
        get_pending_flows_uc=get_pending_flows_uc,
        entity_port=entity_port,
        position_port=position_port,
    )


# ---------------------------------------------------------------------------
# TestPeriodicFlowEvents
# ---------------------------------------------------------------------------


class TestPeriodicFlowEvents:
    @pytest.mark.asyncio
    async def test_creates_events_for_periodic_flows_in_range(self):
        flow = _periodic_flow(
            name="Monthly salary",
            amount=Dezimal(2000),
            flow_type=FlowType.EARNING,
            frequency=FlowFrequency.MONTHLY,
            next_date=date(2025, 4, 10),
        )
        uc = _build_use_case(periodic_flows=[flow])
        query = MoneyEventQuery(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30))

        result = await uc.execute(query)

        periodic_events = [
            e for e in result.events if e.type == MoneyEventType.PERIODIC_FLOW
        ]
        assert len(periodic_events) >= 1
        event = periodic_events[0]
        assert event.name == "Monthly salary"
        assert event.amount == Dezimal(2000)
        assert event.date == date(2025, 4, 10)
        assert event.currency == "EUR"

    @pytest.mark.asyncio
    async def test_negates_expense_amount(self):
        flow = _periodic_flow(
            name="Rent",
            amount=Dezimal(100),
            flow_type=FlowType.EXPENSE,
            frequency=FlowFrequency.MONTHLY,
            next_date=date(2025, 4, 5),
        )
        uc = _build_use_case(periodic_flows=[flow])
        query = MoneyEventQuery(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30))

        result = await uc.execute(query)

        periodic_events = [
            e for e in result.events if e.type == MoneyEventType.PERIODIC_FLOW
        ]
        assert len(periodic_events) == 1
        assert periodic_events[0].amount == Dezimal(-100)

    @pytest.mark.asyncio
    async def test_skips_flow_without_next_date(self):
        flow = _periodic_flow(
            name="No date flow",
            next_date=None,
        )
        uc = _build_use_case(periodic_flows=[flow])
        query = MoneyEventQuery(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30))

        result = await uc.execute(query)

        periodic_events = [
            e for e in result.events if e.type == MoneyEventType.PERIODIC_FLOW
        ]
        assert len(periodic_events) == 0


# ---------------------------------------------------------------------------
# TestPendingFlowEvents
# ---------------------------------------------------------------------------


class TestPendingFlowEvents:
    @pytest.mark.asyncio
    async def test_creates_event_for_enabled_pending_flow_in_range(self):
        flow = _pending_flow(
            name="Tax refund",
            amount=Dezimal(300),
            flow_type=FlowType.EARNING,
            enabled=True,
            flow_date=date(2025, 4, 15),
        )
        uc = _build_use_case(pending_flows=[flow])
        query = MoneyEventQuery(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30))

        result = await uc.execute(query)

        pending_events = [
            e for e in result.events if e.type == MoneyEventType.PENDING_FLOW
        ]
        assert len(pending_events) == 1
        event = pending_events[0]
        assert event.name == "Tax refund"
        assert event.amount == Dezimal(300)
        assert event.date == date(2025, 4, 15)

    @pytest.mark.asyncio
    async def test_skips_disabled_pending_flow(self):
        flow = _pending_flow(
            name="Disabled flow",
            enabled=False,
            flow_date=date(2025, 4, 15),
        )
        uc = _build_use_case(pending_flows=[flow])
        query = MoneyEventQuery(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30))

        result = await uc.execute(query)

        pending_events = [
            e for e in result.events if e.type == MoneyEventType.PENDING_FLOW
        ]
        assert len(pending_events) == 0

    @pytest.mark.asyncio
    async def test_skips_pending_flow_outside_range(self):
        flow = _pending_flow(
            name="Out of range",
            enabled=True,
            flow_date=date(2025, 6, 1),
        )
        uc = _build_use_case(pending_flows=[flow])
        query = MoneyEventQuery(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30))

        result = await uc.execute(query)

        pending_events = [
            e for e in result.events if e.type == MoneyEventType.PENDING_FLOW
        ]
        assert len(pending_events) == 0


# ---------------------------------------------------------------------------
# TestEventSorting
# ---------------------------------------------------------------------------


class TestEventSorting:
    @pytest.mark.asyncio
    async def test_events_sorted_by_date_then_type_then_name(self):
        # Pending flow on April 10 — type "PENDING_FLOW" sorts before "PERIODIC_FLOW"
        pending = _pending_flow(
            name="Insurance",
            flow_type=FlowType.EXPENSE,
            enabled=True,
            flow_date=date(2025, 4, 10),
        )
        # Periodic flow on April 10 — same date, type "PERIODIC_FLOW" sorts after "PENDING_FLOW"
        periodic_same_day = _periodic_flow(
            name="Salary",
            flow_type=FlowType.EARNING,
            frequency=FlowFrequency.MONTHLY,
            next_date=date(2025, 4, 10),
        )
        # Periodic flow on April 5 — earliest date, should come first
        periodic_earlier = _periodic_flow(
            name="Rent",
            flow_type=FlowType.EXPENSE,
            frequency=FlowFrequency.MONTHLY,
            next_date=date(2025, 4, 5),
        )

        uc = _build_use_case(
            periodic_flows=[periodic_same_day, periodic_earlier],
            pending_flows=[pending],
        )
        query = MoneyEventQuery(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30))

        result = await uc.execute(query)

        assert len(result.events) == 3
        # First: April 5 periodic (earliest date)
        assert result.events[0].date == date(2025, 4, 5)
        assert result.events[0].name == "Rent"
        assert result.events[0].type == MoneyEventType.PERIODIC_FLOW
        # Second: April 10 pending ("PENDING_FLOW" < "PERIODIC_FLOW" alphabetically)
        assert result.events[1].date == date(2025, 4, 10)
        assert result.events[1].type == MoneyEventType.PENDING_FLOW
        assert result.events[1].name == "Insurance"
        # Third: April 10 periodic ("PERIODIC_FLOW" > "PENDING_FLOW" alphabetically)
        assert result.events[2].date == date(2025, 4, 10)
        assert result.events[2].type == MoneyEventType.PERIODIC_FLOW
        assert result.events[2].name == "Salary"


# ---------------------------------------------------------------------------
# TestEmptyResults
# ---------------------------------------------------------------------------


class TestEmptyResults:
    @pytest.mark.asyncio
    async def test_returns_empty_events_when_no_data(self):
        uc = _build_use_case()
        query = MoneyEventQuery(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30))

        result = await uc.execute(query)

        assert result.events == []
        assert len(result.events) == 0
