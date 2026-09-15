from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.dezimal import Dezimal
from domain.instrument import InstrumentDataRequest, InstrumentType
from infrastructure.client.instrument.finect_client import FinectClient


def _make_client() -> FinectClient:
    client = FinectClient.__new__(FinectClient)
    client._session = MagicMock()
    import logging

    client._log = logging.getLogger(__name__)
    return client


def _fund_search_item(isin: str, product_id: str, item_type: str = "fund") -> dict:
    return {
        "id": product_id,
        "type": item_type,
        "title": "Some fund",
        "entity": {"id": product_id, "isin": isin},
    }


@pytest.mark.asyncio
async def test_get_history_resolves_id_and_parses_timeseries():
    client = _make_client()
    client._search_raw = AsyncMock(
        return_value=[_fund_search_item("ES0164469001", "efb8b08c")]
    )
    client._get_timeseries = AsyncMock(
        return_value=[
            {"datetime": "2018-03-20T00:00:00.000Z", "price": 5},
            {"datetime": "2018-03-21T00:00:00.000Z", "price": 4.993},
        ]
    )
    request = InstrumentDataRequest(
        type=InstrumentType.MUTUAL_FUND, isin="ES0164469001", currency="EUR"
    )

    points, symbol, source = await client.get_history(
        request, date(2018, 3, 1), date(2018, 3, 31)
    )

    assert symbol == "efb8b08c"
    assert source == "finect"
    assert len(points) == 2
    assert points[0].date == date(2018, 3, 20)
    assert points[0].price == Dezimal("5")
    assert points[0].currency == "EUR"
    assert points[1].price == Dezimal("4.993")
    client._get_timeseries.assert_awaited_once_with(
        "funds", "efb8b08c", date(2018, 3, 1)
    )


@pytest.mark.asyncio
async def test_get_history_etf_uses_etfs_path():
    client = _make_client()
    client._search_raw = AsyncMock(
        return_value=[_fund_search_item("IE00B4L5Y983", "abc12345", item_type="etf")]
    )
    client._get_timeseries = AsyncMock(
        return_value=[{"datetime": "2020-01-02T00:00:00.000Z", "price": 10}]
    )
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="IE00B4L5Y983")

    points, _, _ = await client.get_history(
        request, date(2020, 1, 1), date(2020, 1, 31)
    )

    assert len(points) == 1
    client._get_timeseries.assert_awaited_once_with(
        "etfs", "abc12345", date(2020, 1, 1)
    )


@pytest.mark.asyncio
async def test_get_history_returns_empty_when_no_matching_isin():
    client = _make_client()
    client._search_raw = AsyncMock(
        return_value=[_fund_search_item("OTHER1234567", "xxx")]
    )
    client._get_timeseries = AsyncMock()
    request = InstrumentDataRequest(
        type=InstrumentType.MUTUAL_FUND, isin="ES0164469001"
    )

    points, symbol, source = await client.get_history(
        request, date(2018, 3, 1), date(2018, 3, 31)
    )

    assert points == []
    assert symbol is None
    assert source is None
    client._get_timeseries.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_history_filters_points_outside_range():
    client = _make_client()
    client._search_raw = AsyncMock(
        return_value=[_fund_search_item("ES0164469001", "efb8b08c")]
    )
    client._get_timeseries = AsyncMock(
        return_value=[
            {"datetime": "2018-02-20T00:00:00.000Z", "price": 1},
            {"datetime": "2018-03-20T00:00:00.000Z", "price": 2},
            {"datetime": "2018-04-20T00:00:00.000Z", "price": 3},
        ]
    )
    request = InstrumentDataRequest(
        type=InstrumentType.MUTUAL_FUND, isin="ES0164469001"
    )

    points, _, _ = await client.get_history(
        request, date(2018, 3, 1), date(2018, 3, 31)
    )

    assert [p.date for p in points] == [date(2018, 3, 20)]
    assert points[0].price == Dezimal("2")


@pytest.mark.asyncio
async def test_get_history_empty_timeseries_returns_empty():
    client = _make_client()
    client._search_raw = AsyncMock(
        return_value=[_fund_search_item("ES0164469001", "efb8b08c")]
    )
    client._get_timeseries = AsyncMock(return_value=[])
    request = InstrumentDataRequest(
        type=InstrumentType.MUTUAL_FUND, isin="ES0164469001"
    )

    points, symbol, source = await client.get_history(
        request, date(2018, 3, 1), date(2018, 3, 31)
    )

    assert points == []
    assert symbol is None
    assert source is None


@pytest.mark.asyncio
async def test_adapter_prefers_finect_history_for_funds():
    from infrastructure.client.instrument.instrument_provider_adapter import (
        InstrumentProviderAdapter,
    )

    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(
        type=InstrumentType.MUTUAL_FUND, isin="ES0164469001"
    )
    expected = [MagicMock()]
    adapter._finect = AsyncMock()
    adapter._finect.get_history = AsyncMock(
        return_value=(expected, "efb8b08c", "finect")
    )
    adapter._yf = AsyncMock()

    points, symbol, source = await adapter.get_history(
        request, date(2018, 3, 1), date(2018, 3, 31)
    )

    assert points == expected
    assert symbol == "efb8b08c"
    assert source == "finect"
    adapter._yf.get_history.assert_not_called()


@pytest.mark.asyncio
async def test_adapter_falls_back_to_yf_when_finect_empty():
    from infrastructure.client.instrument.instrument_provider_adapter import (
        InstrumentProviderAdapter,
    )

    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(
        type=InstrumentType.MUTUAL_FUND, isin="ES0164469001"
    )
    expected = [MagicMock()]
    adapter._finect = AsyncMock()
    adapter._finect.get_history = AsyncMock(return_value=([], None, None))
    adapter._yf = AsyncMock()
    adapter._yf.get_history = AsyncMock(return_value=(expected, "FUND.MC", "yfinance"))

    points, symbol, source = await adapter.get_history(
        request, date(2018, 3, 1), date(2018, 3, 31)
    )

    assert points == expected
    assert symbol == "FUND.MC"
    assert source == "yfinance"


@pytest.mark.asyncio
async def test_adapter_skips_finect_for_stocks():
    from infrastructure.client.instrument.instrument_provider_adapter import (
        InstrumentProviderAdapter,
    )

    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(type=InstrumentType.STOCK, ticker="AAPL")
    expected = [MagicMock()]
    adapter._finect = AsyncMock()
    adapter._yf = AsyncMock()
    adapter._yf.get_history = AsyncMock(return_value=(expected, "AAPL", "yfinance"))

    points, _, _ = await adapter.get_history(
        request, date(2018, 3, 1), date(2018, 3, 31)
    )

    assert points == expected
    adapter._finect.get_history.assert_not_called()


@pytest.mark.asyncio
async def test_get_history_uses_preferred_finect_symbol_without_search():
    client = _make_client()
    client._search_raw = AsyncMock()
    client._get_timeseries = AsyncMock(
        return_value=[{"datetime": "2020-01-02T00:00:00.000Z", "price": 10}]
    )
    request = InstrumentDataRequest(
        type=InstrumentType.MUTUAL_FUND, isin="ES0164469001", currency="EUR"
    )

    points, symbol, source = await client.get_history(
        request, date(2020, 1, 1), date(2020, 1, 31), "efb8b08c"
    )

    assert len(points) == 1
    assert symbol == "efb8b08c"
    assert source == "finect"
    client._search_raw.assert_not_awaited()
    client._get_timeseries.assert_awaited_once_with(
        "funds", "efb8b08c", date(2020, 1, 1)
    )


@pytest.mark.asyncio
async def test_adapter_routes_finect_source_to_finect_client():
    from infrastructure.client.instrument.instrument_provider_adapter import (
        InstrumentProviderAdapter,
    )

    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(
        type=InstrumentType.MUTUAL_FUND, isin="ES0164469001"
    )
    expected = [MagicMock()]
    adapter._finect = AsyncMock()
    adapter._finect.get_history = AsyncMock(
        return_value=(expected, "efb8b08c", "finect")
    )
    adapter._yf = AsyncMock()

    points, symbol, source = await adapter.get_history(
        request, date(2020, 1, 1), date(2020, 1, 31), "efb8b08c", "finect"
    )

    assert points == expected
    adapter._finect.get_history.assert_awaited_once_with(
        request, date(2020, 1, 1), date(2020, 1, 31), "efb8b08c"
    )
    adapter._yf.get_history.assert_not_called()


@pytest.mark.asyncio
async def test_adapter_never_passes_finect_symbol_to_yf():
    from infrastructure.client.instrument.instrument_provider_adapter import (
        InstrumentProviderAdapter,
    )

    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(
        type=InstrumentType.MUTUAL_FUND, isin="ES0164469001"
    )
    adapter._finect = AsyncMock()
    adapter._finect.get_history = AsyncMock(return_value=([], None, None))
    adapter._yf = AsyncMock()
    adapter._yf.get_history = AsyncMock(return_value=([], None, None))
    adapter._yf.get_splits = AsyncMock(return_value=[])

    await adapter.get_history(
        request, date(2018, 3, 1), date(2018, 3, 31), "efb8b08c", "finect"
    )
    await adapter.get_splits(
        request, date(2018, 3, 1), date(2018, 3, 31), "efb8b08c", "finect"
    )

    assert adapter._yf.get_history.await_args.args[3] is None
    assert adapter._yf.get_splits.await_args.args[3] is None
