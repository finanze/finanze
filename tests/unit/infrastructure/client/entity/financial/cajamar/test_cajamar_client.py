import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from infrastructure.client.entity.financial.cajamar.cajamar_client import (
    CajamarClient,
    CajamarSignatureRequired,
)


def _client():
    with patch(
        "infrastructure.client.entity.financial.cajamar.cajamar_client.get_http_session"
    ):
        client = CajamarClient()
    client._post_request = AsyncMock(return_value={"ok": True})
    return client


@pytest.mark.asyncio
async def test_get_loan_omits_arorigin_when_origin_missing():
    client = _client()

    await client.get_loan("17875913980340395546")

    client._post_request.assert_awaited_once_with(
        "/v19.39.0/account/17875913980340395546/loan",
        params=None,
    )


@pytest.mark.asyncio
async def test_get_loan_sends_origin_when_set():
    client = _client()

    await client.get_loan("17875913980340395546", origin="C")

    client._post_request.assert_awaited_once_with(
        "/v19.39.0/account/17875913980340395546/loan",
        params={"arorigin": "C"},
    )


@pytest.mark.asyncio
async def test_login_sends_user_validation():
    client = _client()

    await client._login("secret")

    client._post_request.assert_awaited_once_with(
        "/login",
        body={
            "appVersion": CajamarClient.APP_VERSION,
            "deviceName": "LG G2",
            "hasScreenLock": True,
            "jailbreak": False,
            "language": "eng",
            "osVersion": "29 (10)",
            "password": "secret",
            "screenHeight": 1920,
            "screenWidth": 1080,
            "userValidation": True,
        },
        raw=True,
    )


@pytest.mark.asyncio
async def test_fidis_leasing_confirming_paths():
    client = _client()

    await client.get_fidis_intro()
    await client.get_fidis_details(2, "optk-1")
    await client.get_leasing("lease-9", association="A1")
    await client.get_leasing("lease-9")
    await client.get_confirming("conf-3")

    assert client._post_request.await_args_list == [
        ((CajamarClient.API_VERSION + "/FIDIS",),),
        (
            (CajamarClient.API_VERSION + "/FIDIS/details",),
            {"body": {"index": 2, "optk": "optk-1"}},
        ),
        (
            (CajamarClient.API_VERSION + "/leasing/lease-9",),
            {"body": {"association": "A1"}},
        ),
        (
            (CajamarClient.API_VERSION + "/leasing/lease-9",),
            {"body": {}},
        ),
        ((CajamarClient.API_VERSION + "/confirming/conf-3",),),
    ]


def test_api_version_and_app_version():
    assert CajamarClient.API_VERSION == "/v19.39.0"
    assert CajamarClient.APP_VERSION == "1.143.51"
    assert CajamarClient.BASE_URL == "https://api.cajamar.es/amea-web/abh"


@pytest.mark.asyncio
async def test_get_account_txs_params():
    client = _client()
    path = CajamarClient.API_VERSION + "/account/acc-1/transactions"

    await client.get_account_txs("acc-1", 2, 16)
    await client.get_account_txs(
        "acc-1", 1, 16, date_from=date(2024, 10, 13), date_to=date(2026, 10, 13)
    )
    await client.get_account_txs(
        "acc-1", 3, 16, date_from=date(2024, 10, 13), date_to=date(2026, 10, 13)
    )

    assert client._post_request.await_args_list == [
        ((path,), {"params": {"pageNumber": 2, "pageSize": 16}}),
        ((path,), {"params": {"dateFrom": "2024-10-13", "dateTo": "2026-10-13"}}),
        (
            (path,),
            {
                "params": {
                    "dateFrom": "2024-10-13",
                    "dateTo": "2026-10-13",
                    "pageSize": 16,
                    "pageNumber": 3,
                }
            },
        ),
    ]


def _raw_response(status, body):
    response = MagicMock()
    response.ok = 200 <= status < 300
    response.status = status
    response.text = AsyncMock(
        return_value=body if isinstance(body, str) else json.dumps(body)
    )
    response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            f"HTTP {status}", request=MagicMock(), response=MagicMock()
        )
    )
    return response


def _session_client(response):
    client = _client()
    del client._post_request
    client._session = MagicMock()
    client._session.request = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_get_account_txs_raises_signature_required_on_sgn000():
    client = _session_client(
        _raw_response(
            500,
            {
                "code": "SGN000",
                "message": "Please activate PhoneSign",
                "errorId": None,
            },
        )
    )

    with pytest.raises(CajamarSignatureRequired):
        await client.get_account_txs(
            "acc-1", 1, 16, date_from=date(2024, 10, 14), date_to=date(2026, 10, 14)
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [_raw_response(500, {"code": "E0001"}), _raw_response(500, "not json")],
)
async def test_get_account_txs_raises_http_error_on_other_failures(response):
    client = _session_client(response)

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_account_txs("acc-1", 1, 16)
