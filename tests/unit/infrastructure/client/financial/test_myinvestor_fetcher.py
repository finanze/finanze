from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.dezimal import Dezimal
from infrastructure.client.entity.financial.myinvestor.v2.myinvestor_fetcher import (
    MyInvestorFetcherV2,
)


@pytest.mark.asyncio
async def test_reversed_interest_preserves_negative_amount():
    fetcher = MyInvestorFetcherV2()
    fetcher._client = MagicMock()
    fetcher._client.get_account_movements = AsyncMock(
        return_value={
            "flowList": [
                {
                    "reference": "001849",
                    "operationClass": "0",
                    "operationType": "INTERESES S/F",
                    "operationDate": "2026-08-10T00:00:00.000Z",
                    "currency": "EUR",
                    "concept": "regularizacion intereses julio",
                    "amount": "-0.1800",
                }
            ]
        }
    )

    result = await fetcher._classify_account_txs(
        account={"accountId": "account-id", "accountType": "CASH_ACCOUNT"},
        registered_txs=set(),
        related_security_account_id=None,
        min_date=date.today(),
    )

    interest_tx = result["interests"][0]

    assert interest_tx.amount == Dezimal("-0.18")
    assert interest_tx.retentions == Dezimal("-0.03")
    assert interest_tx.net_amount == Dezimal("-0.15")
