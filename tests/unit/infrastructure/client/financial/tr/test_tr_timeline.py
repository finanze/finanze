import asyncio
from unittest.mock import AsyncMock

import pytest

from infrastructure.client.entity.financial.tr.tr_timeline import TRTimeline


class TestTRTimelineTimeout:
    @pytest.mark.asyncio
    async def test_fetch_returns_collected_events_on_recv_timeout(self):
        tr = AsyncMock()
        tr.timeline_transactions = AsyncMock()
        tr.recv = AsyncMock(side_effect=asyncio.TimeoutError())

        timeline = TRTimeline(tr, requested_data=["timelineTransactions"])
        timeline.events = [{"id": "kept"}]
        timeline.FETCH_TIMEOUT = 0.01

        result = await timeline.fetch()

        assert result == [{"id": "kept"}]
        tr.timeline_transactions.assert_awaited_once()


class TestTRTimelineWithoutDetails:
    @pytest.mark.asyncio
    async def test_returns_timeline_events_without_requesting_details(self):
        tr = AsyncMock()
        tr.timeline_transactions = AsyncMock()
        tr.timeline_detail_v2 = AsyncMock()
        events = [
            {
                "id": "e1",
                "timestamp": "2026-09-20T10:00:00.000+0000",
                "action": {"type": "timelineDetail", "payload": "e1"},
            },
            {
                "id": "e2",
                "timestamp": "2026-09-19T10:00:00.000+0000",
                "action": {"type": "timelineDetail", "payload": "e2"},
            },
        ]
        tr.recv = AsyncMock(
            return_value=(
                None,
                {"type": "timelineTransactions"},
                {"items": events, "cursors": {}},
            )
        )

        timeline = TRTimeline(tr, requested_data=["timelineTransactions"])
        result = await timeline.fetch()

        assert [event["id"] for event in result] == ["e1", "e2"]
        tr.timeline_detail_v2.assert_not_awaited()
