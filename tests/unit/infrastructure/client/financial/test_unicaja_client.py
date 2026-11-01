from unittest.mock import AsyncMock, MagicMock

import pytest

from infrastructure.client.entity.financial.unicaja.unicaja_client import (
    OAUTH_CLIENT_ID,
    UnicajaClient,
)


def _response(body: dict) -> MagicMock:
    response = MagicMock(ok=True)
    response.json = AsyncMock(return_value=body)
    return response


def _logged_client(*responses) -> UnicajaClient:
    client = UnicajaClient()
    client._session = MagicMock()
    client._session.request = AsyncMock(side_effect=list(responses))
    client._username = "user"
    client._token_confirmation = "confirmation"
    return client


@pytest.mark.asyncio
async def test_account_movements_requests_token_and_sends_browser_headers():
    client = _logged_client(
        _response({"token_type": "Bearer", "expires_in": 1800}),
        _response({"movimientos": []}),
    )

    await client.get_account_movements("003")

    token_call, movements_call = client._session.request.call_args_list
    assert token_call.args[1].endswith("/apis/externo/unicaja/univia/oauth2/token")
    assert token_call.kwargs["data"] == {
        "grant_type": "password",
        "client_id": OAUTH_CLIENT_ID,
        "scope": "BD",
        "username": "user",
        "password": "confirmation",
    }
    assert movements_call.kwargs["data"] == {"ppp": "003", "indOperacion": "I"}
    assert movements_call.kwargs["headers"]["Origin"] == (
        "https://univia.unicajabanco.es"
    )
    assert movements_call.kwargs["headers"]["Referer"] == (
        "https://univia.unicajabanco.es/mfe-integration/cuentas/003/movimientos"
    )


@pytest.mark.asyncio
async def test_account_movements_reuses_valid_token():
    client = _logged_client(
        _response({"expires_in": 1800}),
        _response({"movimientos": []}),
        _response({"movimientos": []}),
    )

    await client.get_account_movements("003")
    await client.get_account_movements("003", "10.00", "5")

    assert client._session.request.call_count == 3


@pytest.mark.asyncio
async def test_account_movements_fails_without_token_grant():
    client = _logged_client()
    client._token_confirmation = None

    with pytest.raises(ValueError):
        await client.get_account_movements("003")


@pytest.mark.asyncio
async def test_simulate_movements_signature_returns_signature_data():
    signature = {"coordenada": "**", "telefono": "******447", "referencia": "1"}
    client = _logged_client(_response({"datosfirmaoper": signature}))

    result = await client.simulate_movements_signature("003")

    assert result == signature
    call = client._session.request.call_args
    assert call.args[1].endswith("/services/rest/api/cuentas/simulacionMovimientos")
    assert call.kwargs["data"] == {"ppp": "003", "indProcedencia": "L"}
    assert call.kwargs["headers"]["Referer"].endswith("/cuentas/003/movimientos")


@pytest.mark.asyncio
async def test_sign_movements_succeeds_on_ok_code():
    client = _logged_client(_response({"codigoOK": "OK"}))

    assert await client.sign_movements("003", "**", "282334")
    call = client._session.request.call_args
    assert call.args[1].endswith("/services/rest/api/cuentas/firmaMovimientos")
    assert call.kwargs["data"] == {"coordenada": "**", "dobleCanal": "282334"}


@pytest.mark.asyncio
async def test_sign_movements_fails_on_error_response():
    error = MagicMock(ok=False, status=400)
    client = _logged_client(error, _response({"codigoOK": "KO"}))

    assert not await client.sign_movements("003", "**", "000000")
    assert not await client.sign_movements("003", "**", "000000")
