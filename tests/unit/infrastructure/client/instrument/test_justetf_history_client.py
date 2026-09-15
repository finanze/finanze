import logging
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.dezimal import Dezimal
from domain.instrument import InstrumentDataRequest, InstrumentType
from infrastructure.client.instrument.instrument_provider_adapter import (
    InstrumentProviderAdapter,
)
from infrastructure.client.instrument.justetf_history_client import (
    JustEtfHistoryClient,
)


def _make_client() -> JustEtfHistoryClient:
    client = JustEtfHistoryClient.__new__(JustEtfHistoryClient)
    client._session = MagicMock()
    client._log = logging.getLogger(__name__)
    return client


def _series(*pairs) -> list[dict]:
    return [
        {"date": day, "value": {"raw": value, "localized": str(value)}}
        for day, value in pairs
    ]


@pytest.mark.asyncio
async def test_get_history_parses_absolute_quotes():
    client = _make_client()
    client._get_chart = AsyncMock(
        return_value=_series(("2025-01-02", 602.95), ("2025-01-03", 611.88))
    )
    request = InstrumentDataRequest(
        type=InstrumentType.ETF, isin="IE00B5BMR087", currency="EUR"
    )

    points, symbol, source = await client.get_history(
        request, date(2025, 1, 1), date(2025, 1, 10)
    )

    assert symbol == "IE00B5BMR087"
    assert source == "justetf"
    assert [p.date for p in points] == [date(2025, 1, 2), date(2025, 1, 3)]
    assert points[0].price == Dezimal("602.95")
    assert points[0].currency == "EUR"
    client._get_chart.assert_awaited_once_with(
        "IE00B5BMR087", "EUR", date(2025, 1, 1), date(2025, 1, 10)
    )


@pytest.mark.asyncio
async def test_get_history_filters_outside_requested_range():
    client = _make_client()
    client._get_chart = AsyncMock(
        return_value=_series(("2024-12-30", 1), ("2025-01-05", 2), ("2025-02-01", 3))
    )
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="IE00B5BMR087")

    points, _, _ = await client.get_history(
        request, date(2025, 1, 1), date(2025, 1, 10)
    )

    assert [p.date for p in points] == [date(2025, 1, 5)]


@pytest.mark.asyncio
async def test_get_history_defaults_currency_to_eur():
    client = _make_client()
    client._get_chart = AsyncMock(return_value=_series(("2025-01-02", 10)))
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="IE00B5BMR087")

    points, _, _ = await client.get_history(
        request, date(2025, 1, 1), date(2025, 1, 10)
    )

    assert points[0].currency == "EUR"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "instrument_type", [InstrumentType.MUTUAL_FUND, InstrumentType.STOCK]
)
async def test_get_history_only_serves_etfs(instrument_type):
    client = _make_client()
    client._get_chart = AsyncMock()
    request = InstrumentDataRequest(type=instrument_type, isin="IE00B5BMR087")

    points, symbol, source = await client.get_history(
        request, date(2025, 1, 1), date(2025, 1, 10)
    )

    assert (points, symbol, source) == ([], None, None)
    client._get_chart.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_history_requires_an_isin():
    client = _make_client()
    client._get_chart = AsyncMock()
    request = InstrumentDataRequest(type=InstrumentType.ETF, ticker="VWCE.DE")

    points, symbol, source = await client.get_history(
        request, date(2025, 1, 1), date(2025, 1, 10)
    )

    assert (points, symbol, source) == ([], None, None)
    client._get_chart.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_history_empty_chart_returns_empty():
    client = _make_client()
    client._get_chart = AsyncMock(return_value=[])
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="IE00B5BMR087")

    points, symbol, source = await client.get_history(
        request, date(2025, 1, 1), date(2025, 1, 10)
    )

    assert (points, symbol, source) == ([], None, None)


@pytest.mark.asyncio
async def test_adapter_tries_justetf_before_yfinance_for_etfs():
    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="IE00B5BMR087")
    expected = [MagicMock()]
    adapter._finect = AsyncMock()
    adapter._finect.get_history = AsyncMock(return_value=([], None, None))
    adapter._jeh = AsyncMock()
    adapter._jeh.get_history = AsyncMock(
        return_value=(expected, "IE00B5BMR087", "justetf")
    )
    adapter._yf = AsyncMock()

    points, symbol, source = await adapter.get_history(
        request, date(2025, 1, 1), date(2025, 1, 10)
    )

    assert points == expected
    assert (symbol, source) == ("IE00B5BMR087", "justetf")
    adapter._yf.get_history.assert_not_called()


@pytest.mark.asyncio
async def test_adapter_skips_justetf_for_funds():
    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(
        type=InstrumentType.MUTUAL_FUND, isin="IE00BYX5NX33"
    )
    adapter._finect = AsyncMock()
    adapter._finect.get_history = AsyncMock(return_value=([], None, None))
    adapter._jeh = AsyncMock()
    adapter._yf = AsyncMock()
    adapter._yf.get_history = AsyncMock(return_value=([], None, None))

    await adapter.get_history(request, date(2025, 1, 1), date(2025, 1, 10))

    adapter._jeh.get_history.assert_not_called()


@pytest.mark.asyncio
async def test_adapter_puts_preferred_source_first_and_passes_symbol():
    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="IE00B5BMR087")
    expected = [MagicMock()]
    adapter._finect = AsyncMock()
    adapter._jeh = AsyncMock()
    adapter._jeh.get_history = AsyncMock(
        return_value=(expected, "IE00B5BMR087", "justetf")
    )
    adapter._yf = AsyncMock()

    points, _, _ = await adapter.get_history(
        request, date(2025, 1, 1), date(2025, 1, 10), "IE00B5BMR087", "justetf"
    )

    assert points == expected
    adapter._finect.get_history.assert_not_called()
    adapter._jeh.get_history.assert_awaited_once_with(
        request, date(2025, 1, 1), date(2025, 1, 10), "IE00B5BMR087"
    )


@pytest.mark.asyncio
async def test_adapter_falls_back_when_preferred_provider_returns_nothing():
    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="IE00B5BMR087")
    expected = [MagicMock()]
    adapter._finect = AsyncMock()
    adapter._finect.get_history = AsyncMock(return_value=([], None, None))
    adapter._jeh = AsyncMock()
    adapter._jeh.get_history = AsyncMock(return_value=([], None, None))
    adapter._yf = AsyncMock()
    adapter._yf.get_history = AsyncMock(return_value=(expected, "VWCE.DE", "yfinance"))

    points, symbol, source = await adapter.get_history(
        request, date(2025, 1, 1), date(2025, 1, 10), "IE00B5BMR087", "justetf"
    )

    assert points == expected
    assert (symbol, source) == ("VWCE.DE", "yfinance")
    adapter._yf.get_history.assert_awaited_once_with(
        request, date(2025, 1, 1), date(2025, 1, 10), None
    )


@pytest.mark.asyncio
async def test_adapter_continues_chain_when_provider_raises():
    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="IE00B5BMR087")
    expected = [MagicMock()]
    adapter._finect = AsyncMock()
    adapter._finect.get_history = AsyncMock(side_effect=RuntimeError("boom"))
    adapter._jeh = AsyncMock()
    adapter._jeh.get_history = AsyncMock(
        return_value=(expected, "IE00B5BMR087", "justetf")
    )
    adapter._yf = AsyncMock()

    points, _, source = await adapter.get_history(
        request, date(2025, 1, 1), date(2025, 1, 10)
    )

    assert points == expected
    assert source == "justetf"
