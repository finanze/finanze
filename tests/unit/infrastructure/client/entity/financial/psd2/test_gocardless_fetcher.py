from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from requests.models import HTTPError, Response

from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import TooManyRequests
from domain.external_entity import (
    ExternalEntity,
    ExternalEntityStatus,
    ExternalEntityTxFetchRequest,
)
from domain.external_integration import ExternalIntegrationId
from domain.transactions import TxType
from infrastructure.client.entity.financial.psd2.gocardless_fetcher import (
    GoCardlessFetcher,
)

ENTITY = Entity(
    id=uuid4(),
    name="Bank",
    natural_id="BANKESMM",
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.EXTERNALLY_PROVIDED,
    icon_url=None,
)


def _request(registered=None):
    return ExternalEntityTxFetchRequest(
        external_entity=ExternalEntity(
            id=uuid4(),
            entity_id=ENTITY.id,
            status=ExternalEntityStatus.LINKED,
            provider=ExternalIntegrationId.GOCARDLESS,
            date=date(2026, 1, 1),
            provider_instance_id="req-1",
            payload=None,
        ),
        entity=ENTITY,
        from_date=date(2026, 8, 1),
        registered_txs=registered or set(),
    )


def _fetcher():
    client = MagicMock()
    client.get_requisition.return_value = {"accounts": ["acc-1", "acc-2"]}
    client.get_account_details.side_effect = lambda account_id: {
        "account": {
            "iban": "ES111" if account_id == "acc-1" else None,
            "status": "deleted" if account_id == "acc-2" else "enabled",
        }
    }
    client.get_account_transactions.return_value = {
        "transactions": {
            "booked": [
                {
                    "transactionId": "T1",
                    "bookingDate": "2026-09-01",
                    "transactionAmount": {"amount": "-20.50", "currency": "EUR"},
                    "creditorName": "Shop",
                    "remittanceInformationUnstructured": "Card payment",
                },
                {
                    "transactionId": "T2",
                    "bookingDate": "2026-09-02",
                    "transactionAmount": {"amount": "1500", "currency": "EUR"},
                    "debtorName": "ACME",
                    "remittanceInformationUnstructured": "Payroll",
                },
            ],
            "pending": [
                {
                    "transactionAmount": {"amount": "-1", "currency": "EUR"},
                    "bookingDate": "2026-09-03",
                }
            ],
        }
    }
    return GoCardlessFetcher(client), client


@pytest.mark.asyncio
async def test_maps_booked_transactions_and_skips_registered():
    fetcher, client = _fetcher()

    result = await fetcher.transactions(_request(registered={"ES111:T1"}))

    assert [(tx.ref, tx.type) for tx in result.account] == [("ES111:T2", TxType.INFLOW)]
    assert result.account[0].iban == "ES111"
    client.get_account_transactions.assert_called_once_with(
        "acc-1", date_from="2026-08-01"
    )


@pytest.mark.asyncio
async def test_rate_limit_is_propagated():
    fetcher, client = _fetcher()
    response = Response()
    response.status_code = 429
    client.get_account_transactions.side_effect = HTTPError(response=response)

    with pytest.raises(TooManyRequests):
        await fetcher.transactions(_request())
