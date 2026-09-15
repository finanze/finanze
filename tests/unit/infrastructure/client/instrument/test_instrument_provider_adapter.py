from unittest.mock import AsyncMock

import pytest

from domain.dezimal import Dezimal
from domain.instrument import (
    InstrumentDataRequest,
    InstrumentInfo,
    InstrumentOverview,
    InstrumentType,
)
from infrastructure.client.instrument.instrument_provider_adapter import (
    InstrumentProviderAdapter,
)


@pytest.mark.asyncio
async def test_stock_search_falls_back_to_yfinance_when_tradingview_returns_no_results():
    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(type=InstrumentType.STOCK, ticker="AAPL")
    expected = [
        InstrumentOverview(
            name="Apple Inc.",
            symbol="AAPL",
            type=InstrumentType.STOCK,
        )
    ]
    adapter._tv = AsyncMock()
    adapter._tv.search = AsyncMock(return_value=[])
    adapter._yf = AsyncMock()
    adapter._yf.lookup = AsyncMock(return_value=expected)

    results = await adapter._stock_search(request)

    assert results == expected
    adapter._tv.search.assert_awaited_once_with(request)
    adapter._yf.lookup.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_fund_search_falls_back_to_ft_when_finect_returns_no_results():
    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(type=InstrumentType.MUTUAL_FUND, name="Fund")
    expected = [
        InstrumentOverview(
            name="Fund result",
            type=InstrumentType.MUTUAL_FUND,
        )
    ]
    adapter._finect = AsyncMock()
    adapter._finect.search = AsyncMock(return_value=[])
    adapter._ft = AsyncMock()
    adapter._ft.search = AsyncMock(return_value=expected)
    adapter._yf = AsyncMock()
    adapter._yf.lookup = AsyncMock(return_value=[])

    results = await adapter._fund_etf_search(request)

    assert results == expected
    adapter._finect.search.assert_awaited_once_with(request)
    adapter._ft.search.assert_awaited_once_with(request)
    adapter._yf.lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_etf_search_falls_through_empty_providers_to_yfinance():
    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="IE00TEST")
    expected = [
        InstrumentOverview(
            isin="IE00TEST",
            name="ETF result",
            type=InstrumentType.ETF,
        )
    ]
    calls = []

    async def finect_search(_request):
        calls.append("finect")
        return []

    async def ft_search(_request):
        calls.append("ft")
        return []

    async def extraetf_search(_request):
        calls.append("ee")
        return []

    async def yfinance_lookup(_request):
        calls.append("yf")
        return expected

    adapter._finect = AsyncMock()
    adapter._finect.search = AsyncMock(side_effect=finect_search)
    adapter._ft = AsyncMock()
    adapter._ft.search = AsyncMock(side_effect=ft_search)
    adapter._ee = AsyncMock()
    adapter._ee.search = AsyncMock(side_effect=extraetf_search)
    adapter._yf = AsyncMock()
    adapter._yf.lookup = AsyncMock(side_effect=yfinance_lookup)
    adapter._le = AsyncMock()
    adapter._le.search = AsyncMock(return_value=[])

    results = await adapter._fund_etf_search(request)

    assert results == expected
    assert calls == ["finect", "ft", "ee", "yf"]
    adapter._le.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_etf_search_falls_back_to_local_etf_when_other_providers_return_no_results():
    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="IE00TEST")
    expected = [
        InstrumentOverview(
            isin="IE00TEST",
            name="Local ETF result",
            type=InstrumentType.ETF,
        )
    ]
    adapter._finect = AsyncMock()
    adapter._finect.search = AsyncMock(return_value=[])
    adapter._ft = AsyncMock()
    adapter._ft.search = AsyncMock(return_value=[])
    adapter._ee = AsyncMock()
    adapter._ee.search = AsyncMock(return_value=[])
    adapter._yf = AsyncMock()
    adapter._yf.lookup = AsyncMock(return_value=[])
    adapter._le = AsyncMock()
    adapter._le.search = AsyncMock(return_value=expected)

    results = await adapter._fund_etf_search(request)

    assert results == expected
    adapter._le.search.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_instrument_info_falls_back_to_justetf_when_yfinance_returns_no_info():
    adapter = InstrumentProviderAdapter(enabled_clients=[])
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="IE00TEST")
    expected = InstrumentInfo(
        name="ETF result",
        currency="EUR",
        type=InstrumentType.ETF,
        price=Dezimal("10.00"),
    )
    adapter._finect = AsyncMock()
    adapter._finect.get_instrument_info = AsyncMock(return_value=None)
    adapter._yf = AsyncMock()
    adapter._yf.get_instrument_info = AsyncMock(return_value=None)
    adapter._je = AsyncMock()
    adapter._je.get_instrument_info = AsyncMock(return_value=expected)
    adapter._ee = AsyncMock()
    adapter._ee.get_instrument_info = AsyncMock()

    result = await adapter._get_instrument_info(request.isin, request.type)

    assert result == expected
    adapter._finect.get_instrument_info.assert_awaited_once_with(
        request.isin, request.type
    )
    adapter._yf.get_instrument_info.assert_awaited_once_with(request.isin, request.type)
    adapter._je.get_instrument_info.assert_awaited_once_with(request.isin, request.type)
    adapter._ee.get_instrument_info.assert_not_awaited()
