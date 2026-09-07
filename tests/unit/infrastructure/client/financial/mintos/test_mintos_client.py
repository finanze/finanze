from unittest.mock import AsyncMock

import pytest

from infrastructure.client.entity.financial.mintos.mintos_client import MintosAPIClient


@pytest.mark.asyncio
@pytest.mark.parametrize("resource", ["positions", "transactions", "orders"])
async def test_asset_pagination(resource):
    client = MintosAPIClient()
    client._get_request = AsyncMock(
        side_effect=[
            {"content": [{"id": "first"}], "metadata": {"hasNext": True}},
            {"content": [{"id": "second"}], "metadata": {"hasNext": False}},
        ]
    )

    result = await getattr(client, f"get_asset_{resource}")("account")

    assert result == [{"id": "first"}, {"id": "second"}]
    assert client._get_request.await_args_list[0].kwargs["params"] == {
        "page": 0,
        "size": 30,
    }
    client._get_request.assert_awaited_with(
        f"/assetx-api/v1/accounts/account/{resource}", params={"page": 1, "size": 30}
    )


@pytest.mark.asyncio
async def test_get_etf_details():
    client = MintosAPIClient()
    client._get_request = AsyncMock(
        return_value={"fundProvider": {"title": "HSBC ETF"}}
    )

    result = await client.get_etf_details("IE00B5L01S80")

    assert result == {"fundProvider": {"title": "HSBC ETF"}}
    client._get_request.assert_awaited_once_with(
        "/assetx-price-api/v1/instruments/etf/IE00B5L01S80"
    )


@pytest.mark.asyncio
async def test_get_etf_instrument_details():
    client = MintosAPIClient()
    client._get_request = AsyncMock(
        return_value={"kid": {"language": "es", "url": "https://example.test/kid"}}
    )

    result = await client.get_etf_instrument_details("IE00B5L01S80")

    assert result == {"kid": {"language": "es", "url": "https://example.test/kid"}}
    client._get_request.assert_awaited_once_with(
        "/assetx-api/v1/instruments/IE00B5L01S80",
        params={"productType": "SINGLE_ETF"},
    )
