from datetime import date
from unittest.mock import AsyncMock

import pytest

from infrastructure.client.entity.financial.ing.ing_client import INGAPIClient


@pytest.mark.asyncio
@pytest.mark.parametrize("offset,limit", [(0, 100), (100, 50)])
async def test_account_transactions_use_api_uuid_and_iso_dates(offset, limit):
    client = INGAPIClient()
    response = {"result": "stubbed response"}
    client._get_request = AsyncMock(return_value=response)

    result = await client.get_account_transactions(
        "account-uuid",
        date(2026, 7, 4),
        offset=offset,
        limit=limit,
        to_date=date(2026, 10, 4),
    )

    assert result is response
    client._get_request.assert_awaited_once_with(
        "/v2/products/account-uuid/transactions",
        params={
            "limit": limit,
            "offset": offset,
            "fromDate": "2026-07-04",
            "toDate": "2026-10-04",
            "filterEru": "false",
        },
    )
