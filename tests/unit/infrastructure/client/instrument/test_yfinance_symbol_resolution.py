import pytest

from domain.instrument import InstrumentType
from infrastructure.client.instrument.yfinance_client import YFinanceClient


@pytest.mark.parametrize(
    "query",
    [
        "ISHRS EMRG MARKT INDX FND D EU",
        "Fondo Naranja Prudente FI",
        "IE00BYWYCC39",
        "0P0001AINL.F.EXTRA.LONG",
    ],
)
def test_non_ticker_queries_are_not_ticker_shaped(query):
    assert YFinanceClient._looks_like_ticker(query) is False


@pytest.mark.parametrize("query", ["AAPL", "REP.MC", "0P0001AINL.F", "BRK-B", "^GSPC"])
def test_ticker_shaped_queries(query):
    assert YFinanceClient._looks_like_ticker(query) is True


@pytest.mark.asyncio
async def test_empty_lookup_for_name_returns_no_candidates(monkeypatch):
    client = YFinanceClient.__new__(YFinanceClient)

    class _EmptyLookup:
        def __init__(self, query):
            pass

        def get_mutualfund(self):
            return None

    monkeypatch.setattr(
        "infrastructure.client.instrument.yfinance_client.yf.Lookup", _EmptyLookup
    )

    candidates = await client._resolve_symbol_candidates.__wrapped__(
        client, "ISHRS EMRG MARKT INDX FND D EU", InstrumentType.MUTUAL_FUND
    )

    assert candidates == []


@pytest.mark.parametrize(
    "instrument_type",
    [InstrumentType.MUTUAL_FUND, InstrumentType.ETF, InstrumentType.STOCK],
)
@pytest.mark.asyncio
async def test_name_never_becomes_a_ticker_for_any_type(monkeypatch, instrument_type):
    client = YFinanceClient.__new__(YFinanceClient)

    class _EmptyLookup:
        def __init__(self, query):
            pass

        def get_mutualfund(self):
            return None

        get_etf = get_mutualfund
        get_stock = get_mutualfund

    monkeypatch.setattr(
        "infrastructure.client.instrument.yfinance_client.yf.Lookup", _EmptyLookup
    )

    candidates = await client._resolve_symbol_candidates.__wrapped__(
        client, "Vanguard FTSE All-World UCITS ETF", instrument_type
    )

    assert candidates == []


@pytest.mark.asyncio
async def test_name_search_still_returns_symbols_when_lookup_hits(monkeypatch):
    import pandas as pd

    client = YFinanceClient.__new__(YFinanceClient)

    class _HitLookup:
        def __init__(self, query):
            pass

        def get_etf(self):
            return pd.DataFrame(
                {"exchange": ["GER", "AMS"]}, index=["VWCE.DE", "VWRL.AS"]
            )

    monkeypatch.setattr(
        "infrastructure.client.instrument.yfinance_client.yf.Lookup", _HitLookup
    )

    candidates = await client._resolve_symbol_candidates.__wrapped__(
        client, "Vanguard FTSE All-World UCITS ETF", InstrumentType.ETF
    )

    assert set(candidates) == {"VWCE.DE", "VWRL.AS"}
