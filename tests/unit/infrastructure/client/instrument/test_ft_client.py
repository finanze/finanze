from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domain.instrument import InstrumentDataRequest, InstrumentType
from infrastructure.client.instrument.ft_client import FtClient


@pytest.mark.asyncio
async def test_search_uses_impersonated_session_request():
    response = MagicMock(ok=True)
    response.json = AsyncMock(
        return_value={
            "equities": [
                {"name": "Apple Inc.", "symbol": "AAPL:XNAS"},
            ]
        }
    )

    with patch(
        "infrastructure.client.instrument.ft_client.new_impersonated_http_session"
    ) as new_session:
        session = MagicMock()
        session.headers = {}
        session.request = AsyncMock(return_value=response)
        new_session.return_value = session

        client = FtClient()
        results = await client.search(
            InstrumentDataRequest(type=InstrumentType.STOCK, ticker="AAPL")
        )

    assert len(results) == 1
    assert results[0].name == "Apple Inc."
    assert results[0].symbol == "AAPL"
    assert results[0].market == "XNAS"
    assert results[0].type == InstrumentType.STOCK
    new_session.assert_called_once_with()
    session.request.assert_awaited_once_with(
        "GET",
        client.BASE_URL,
        params={"partial": "AAPL", "only": "equities", "count": "100"},
        timeout=10,
    )
