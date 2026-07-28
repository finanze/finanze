from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.dezimal import Dezimal
from domain.instrument import InstrumentDataRequest, InstrumentType
from infrastructure.client.instrument.boursier_client import (
    BoursierClient,
    _parse_price,
)


SEARCH_RESPONSE = [
    {
        "name": "Sycomore Euro IG Short Duration RC",
        "section": "FR001400MT31 - Sicav et FCP",
        "code": "",
        "url": "/opcvm/cours/sycomore-euro-ig-short-duration-rc-FR001400MT31,FR.html",
        "nature": "OPCVM",
        "quote": {"price": "107,120€", "variation": "+0,06%", "css": "up"},
    },
    {
        "name": "A stock",
        "section": "FR0000000001 - Action",
        "nature": "ACTION",
        "quote": {"price": "10,00€"},
    },
]


@pytest.fixture
def client():
    client = BoursierClient()
    response = MagicMock()
    response.ok = True
    response.json = AsyncMock(return_value=SEARCH_RESPONSE)
    client._session = MagicMock()
    client._session.post = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_search_maps_opcvm_and_parses_french_price(client):
    request = InstrumentDataRequest(
        type=InstrumentType.MUTUAL_FUND,
        isin="FR001400MT31",
    )

    results = await client.search(request)

    assert len(results) == 1
    assert results[0].isin == "FR001400MT31"
    assert results[0].name == "Sycomore Euro IG Short Duration RC"
    assert results[0].currency == "EUR"
    assert results[0].symbol is None
    assert results[0].type == InstrumentType.MUTUAL_FUND
    assert results[0].price == Dezimal("107.120")
    client._session.post.assert_awaited_once_with(
        client.BASE_URL,
        data={"q": "FR001400MT31"},
        timeout=10,
    )


@pytest.mark.asyncio
async def test_search_returns_empty_for_non_mutual_fund_request(client):
    request = InstrumentDataRequest(type=InstrumentType.ETF, name="fund")

    assert await client.search(request) == []
    client._session.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_handles_missing_quote(client):
    response = MagicMock()
    response.ok = True
    response.json = AsyncMock(
        return_value=[
            {
                "name": "Fund without quote",
                "section": None,
                "url": None,
                "nature": "OPCVM",
                "quote": None,
            }
        ]
    )
    client._session.post = AsyncMock(return_value=response)

    results = await client.search(
        InstrumentDataRequest(type=InstrumentType.MUTUAL_FUND, name="fund")
    )

    assert len(results) == 1
    assert results[0].price is None
    assert results[0].currency is None
    assert results[0].isin is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1 234,56 €", Dezimal("1234.56")),
        ("1.234,56€", Dezimal("1234.56")),
        ("invalid", None),
        (None, None),
    ],
)
def test_parse_price(raw, expected):
    assert _parse_price(raw) == expected
