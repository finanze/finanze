import pytest
from unittest.mock import patch

from domain.instrument import (
    InstrumentDataRequest,
    InstrumentType,
)
from infrastructure.client.instrument.local_etf_client import LocalEtfClient

SAMPLE_DATA = {
    "DE000A0F5UH1": {
        "wkn": "A0F5UH",
        "ticker": "ISPA",
        "name": "iShares STOXX Global Select Dividend 100 UCITS ETF (DE)",
        "currency": "EUR",
        "isin": "DE000A0F5UH1",
    },
    "IE00B4L5Y983": {
        "wkn": "A0RPWH",
        "ticker": "EUNL",
        "name": "iShares Core MSCI World UCITS ETF USD (Acc)",
        "currency": "USD",
        "isin": "IE00B4L5Y983",
    },
    "LU0290358497": {
        "wkn": "DBX1MW",
        "ticker": "XDWD",
        "name": "Xtrackers MSCI World Swap UCITS ETF 1C",
        "currency": "USD",
        "isin": "LU0290358497",
    },
}


@pytest.fixture
def client():
    c = LocalEtfClient()
    c._data = SAMPLE_DATA
    return c


@pytest.mark.asyncio
async def test_search_by_isin_startswith(client):
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="DE000")
    results = await client.search(request)
    assert len(results) == 1
    assert results[0].isin == "DE000A0F5UH1"
    assert results[0].name == "iShares STOXX Global Select Dividend 100 UCITS ETF (DE)"
    assert results[0].currency == "EUR"
    assert results[0].symbol == "ISPA"
    assert results[0].type == InstrumentType.ETF
    assert results[0].price is None


@pytest.mark.asyncio
async def test_search_by_ticker_startswith(client):
    request = InstrumentDataRequest(type=InstrumentType.ETF, ticker="EUN")
    results = await client.search(request)
    assert len(results) == 1
    assert results[0].isin == "IE00B4L5Y983"


@pytest.mark.asyncio
async def test_search_by_name_startswith_case_insensitive(client):
    request = InstrumentDataRequest(type=InstrumentType.ETF, name="xtrackers")
    results = await client.search(request)
    assert len(results) == 1
    assert results[0].isin == "LU0290358497"


@pytest.mark.asyncio
async def test_search_multiple_matches(client):
    request = InstrumentDataRequest(type=InstrumentType.ETF, name="iShares")
    results = await client.search(request)
    assert len(results) == 2
    isins = {r.isin for r in results}
    assert isins == {"DE000A0F5UH1", "IE00B4L5Y983"}


@pytest.mark.asyncio
async def test_search_no_matches(client):
    request = InstrumentDataRequest(type=InstrumentType.ETF, isin="ZZZZZ")
    results = await client.search(request)
    assert results == []


@pytest.mark.asyncio
async def test_search_non_etf_returns_empty(client):
    request = InstrumentDataRequest(type=InstrumentType.STOCK, name="iShares")
    results = await client.search(request)
    assert results == []


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty(client):
    request = InstrumentDataRequest(type=InstrumentType.ETF)
    results = await client.search(request)
    assert results == []


@pytest.mark.asyncio
async def test_get_instrument_info_returns_none(client):
    result = await client.get_instrument_info("DE000A0F5UH1", InstrumentType.ETF)
    assert result is None


@pytest.mark.asyncio
async def test_lazy_load_from_pickle():
    with patch(
        "infrastructure.client.instrument.local_etf_client.pickle.load",
        return_value=SAMPLE_DATA,
    ) as mock_load:
        with patch(
            "builtins.open",
            create=True,
        ) as mock_open:
            client = LocalEtfClient()
            request = InstrumentDataRequest(type=InstrumentType.ETF, isin="DE000")
            results = await client.search(request)
            assert len(results) == 1
            mock_open.assert_called_once()
            mock_load.assert_called_once()

            await client.search(request)
            assert mock_load.call_count == 1
