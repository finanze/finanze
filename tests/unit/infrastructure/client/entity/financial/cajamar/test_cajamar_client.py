import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from infrastructure.client.entity.financial.cajamar.cajamar_client import CajamarClient


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
    return response


@pytest.mark.asyncio
async def test_sign_account_txs_returns_signed_page():
    client = _client()
    page = {"accountTransactionsPagination": {"dataList": [], "pagination": {}}}
    client._post_request = AsyncMock(return_value=_raw_response(200, page))

    result = await client.sign_account_txs("acc-1", "optk-1")

    assert result == page
    client._post_request.assert_awaited_once_with(
        CajamarClient.API_VERSION + "/account/acc-1/transactions/signature",
        body={"optk": "optk-1"},
        raw=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        _raw_response(200, {"type": "PIN", "optk": "optk-1"}),
        _raw_response(200, "not json"),
        _raw_response(403, {"code": "E0001"}),
    ],
)
async def test_sign_account_txs_returns_none_when_not_signed(response):
    client = _client()
    client._post_request = AsyncMock(return_value=response)

    assert await client.sign_account_txs("acc-1", "optk-1") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [httpx.ReadTimeout("timeout"), httpx.NetworkError("CapacitorHttp error")],
)
async def test_sign_account_txs_returns_none_on_transport_error(error):
    client = _client()
    client._post_request = AsyncMock(side_effect=error)

    assert await client.sign_account_txs("acc-1", "optk-1") is None
