from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.use_cases.get_periodic_flows import GetPeriodicFlowsImpl, get_next_date
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow


def _flow(
    frequency: FlowFrequency = FlowFrequency.MONTHLY,
    enabled: bool = True,
    since: date = date(2024, 1, 1),
    until: date | None = None,
    flow_type: FlowType = FlowType.EXPENSE,
    **overrides,
) -> PeriodicFlow:
    defaults = dict(
        id=uuid4(),
        name="Test flow",
        amount=Dezimal(100),
        currency="EUR",
        flow_type=flow_type,
        frequency=frequency,
        category="general",
        enabled=enabled,
        since=since,
        until=until,
        icon=None,
        linked=None,
        next_date=None,
        max_amount=None,
    )
    defaults.update(overrides)
    return PeriodicFlow(**defaults)


def _build_use_case(port=None) -> GetPeriodicFlowsImpl:
    if port is None:
        port = MagicMock()
        port.get_all = AsyncMock(return_value=[])
    return GetPeriodicFlowsImpl(periodic_flow_port=port)


# ---------------------------------------------------------------------------
# TestGetNextDate
# ---------------------------------------------------------------------------


class TestGetNextDate:
    def test_returns_none_when_disabled(self):
        flow = _flow(enabled=False, since=date(2024, 1, 1))

        result = get_next_date(flow)

        assert result is None

    def test_returns_since_date_when_in_future(self):
        tomorrow = date.today() + timedelta(days=1)
        flow = _flow(since=tomorrow)

        result = get_next_date(flow)

        assert result == tomorrow

    def test_daily_returns_tomorrow(self):
        yesterday = date.today() - timedelta(days=1)
        flow = _flow(frequency=FlowFrequency.DAILY, since=yesterday)

        result = get_next_date(flow)

        assert result == date.today() + timedelta(days=1)

    def test_monthly_returns_next_month(self):
        today = date.today()
        # Set since to the 1st of last month so next occurrence is 1st of this or next month
        if today.month == 1:
            since = date(today.year - 1, 12, 1)
        else:
            since = date(today.year, today.month - 1, 1)

        flow = _flow(frequency=FlowFrequency.MONTHLY, since=since)

        result = get_next_date(flow)

        assert result is not None
        assert result > today
        # Monthly from the 1st, so the result should land on the 1st of some month
        assert result.day == 1

    def test_weekly_returns_correct_next_week(self):
        today = date.today()
        since = today - timedelta(days=14)
        flow = _flow(frequency=FlowFrequency.WEEKLY, since=since)

        result = get_next_date(flow)

        assert result is not None
        assert result > today
        # Next occurrence must be within 7 days
        assert result <= today + timedelta(days=7)
        # The gap from since should be a multiple of 7 days
        assert (result - since).days % 7 == 0

    def test_yearly_returns_next_year(self):
        today = date.today()
        since = date(today.year - 1, today.month, today.day)
        flow = _flow(frequency=FlowFrequency.YEARLY, since=since)

        result = get_next_date(flow)

        assert result is not None
        assert result > today
        assert result.year >= today.year

    def test_returns_none_when_next_date_past_until(self):
        yesterday = date.today() - timedelta(days=1)
        flow = _flow(
            frequency=FlowFrequency.DAILY,
            since=date(2024, 1, 1),
            until=yesterday,
        )

        result = get_next_date(flow)

        assert result is None

    def test_quarterly_frequency(self):
        today = date.today()
        # Set since to 6 months ago (1st of that month)
        if today.month > 6:
            since = date(today.year, today.month - 6, 1)
        else:
            since = date(today.year - 1, today.month + 6, 1)

        flow = _flow(frequency=FlowFrequency.QUARTERLY, since=since)

        result = get_next_date(flow)

        assert result is not None
        assert result > today
        # The difference from since should be a multiple of 3 months
        # Verify the day matches
        assert result.day == since.day


# ---------------------------------------------------------------------------
# TestGetPeriodicFlowsExecute
# ---------------------------------------------------------------------------


class TestGetPeriodicFlowsExecute:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_flows(self):
        port = MagicMock()
        port.get_all = AsyncMock(return_value=[])
        uc = _build_use_case(port=port)

        result = await uc.execute()

        assert result == []

    @pytest.mark.asyncio
    async def test_populates_next_date_on_flows(self):
        yesterday = date.today() - timedelta(days=1)
        flows = [
            _flow(frequency=FlowFrequency.DAILY, since=yesterday),
            _flow(frequency=FlowFrequency.MONTHLY, since=date(2024, 1, 1)),
        ]
        port = MagicMock()
        port.get_all = AsyncMock(return_value=flows)
        uc = _build_use_case(port=port)

        result = await uc.execute()

        assert len(result) == 2
        for r in result:
            assert r.next_date is not None

    @pytest.mark.asyncio
    async def test_preserves_flow_fields(self):
        flow_id = uuid4()
        original = _flow(
            id=flow_id,
            name="Rent",
            amount=Dezimal("750.50"),
            currency="USD",
            flow_type=FlowType.EXPENSE,
            frequency=FlowFrequency.MONTHLY,
            category="housing",
            enabled=True,
            since=date(2024, 1, 1),
            until=date(2030, 12, 31),
            icon="home",
            linked=True,
            max_amount=Dezimal("1000"),
        )
        port = MagicMock()
        port.get_all = AsyncMock(return_value=[original])
        uc = _build_use_case(port=port)

        result = await uc.execute()

        assert len(result) == 1
        out = result[0]
        assert out.id == flow_id
        assert out.name == "Rent"
        assert out.amount == Dezimal("750.50")
        assert out.currency == "USD"
        assert out.flow_type == FlowType.EXPENSE
        assert out.frequency == FlowFrequency.MONTHLY
        assert out.category == "housing"
        assert out.enabled is True
        assert out.since == date(2024, 1, 1)
        assert out.until == date(2030, 12, 31)
        assert out.icon == "home"
        assert out.linked is True
        assert out.max_amount == Dezimal("1000")
        assert out.next_date is not None
