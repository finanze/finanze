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
