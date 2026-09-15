from unittest.mock import AsyncMock, patch

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
