from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from infrastructure.client.entity.financial.ing import ing_client as ing_client_module
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


def _session(headers=None, response=None):
    http_response = MagicMock(ok=True)
    http_response.json = AsyncMock(return_value=response or {})
    session = MagicMock()
    session.headers = dict(headers or {})
    session.request = AsyncMock(return_value=http_response)
    return session


def _session_payload(**kwargs):
    return {
        "genomaCookie": "JSESSIONID=abc; XSRF-TOKEN=xsrf-value; other=1",
        "genomaSessionId": "genoma-session",
        "apiCookie": "api-cookie",
        "apiAuth": "Bearer old-token",
        "apiExtendedSessionCtx": "ctx",
        **kwargs,
    }


@pytest.mark.parametrize(
    "payload,expected",
    [
        (_session_payload(genomaLoginCookie="login=1"), True),
        (_session_payload(), False),
    ],
)
def test_inject_session_enables_sca_only_with_genoma_login_cookie(
    monkeypatch, payload, expected
):
    monkeypatch.setattr(ing_client_module, "new_impersonated_http_session", _session)
    client = INGAPIClient()
    client._genoma_session = _session()
    client._api_session = _session()

    client.inject_session(payload)

    assert client.supports_sca() is expected
    if expected:
        assert client._genoma_login_session.headers["Cookie"] == "login=1"


@pytest.mark.asyncio
async def test_start_sca_resets_validations_on_genoma_documentation():
    client = INGAPIClient()
    client._genoma_session = _session(response={"acceptanceMethods": []})

    result = await client.start_sca()

    assert result == {"acceptanceMethods": []}
    client._genoma_session.request.assert_awaited_once_with(
        "GET",
        "https://ing.ingdirect.es/genoma_api/rest/sca/documentation",
        json=None,
        params=None,
        headers={"X-Ing-Reset-Validations": "1"},
    )


@pytest.mark.asyncio
async def test_get_sca_status_polls_genoma_login_session():
    client = INGAPIClient()
    client._genoma_session = _session()
    client._genoma_login_session = _session(response={"resultCode": 0})

    result = await client.get_sca_status("sec-1")

    assert result == {"resultCode": 0}
    client._genoma_session.request.assert_not_awaited()
    client._genoma_login_session.request.assert_awaited_once_with(
        "GET",
        "https://ing.ingdirect.es/genoma_login/rest/getScaStatus",
        json=None,
        params={
            "secProcessId": "sec-1",
            "isLogin": "false",
            "device": "false",
            "model": "false",
            "version": "false",
        },
        headers=None,
        timeout=ing_client_module.SCA_STATUS_TIMEOUT,
    )


@pytest.mark.asyncio
async def test_confirm_sca_sends_process_and_xsrf_token():
    client = INGAPIClient()
    client._genoma_session = _session(
        headers={"Cookie": _session_payload()["genomaCookie"]}
    )

    await client.confirm_sca("sec-1")

    client._genoma_session.request.assert_awaited_once_with(
        "PUT",
        "https://ing.ingdirect.es/genoma_api/rest/sca/documentation",
        json={"processId": "sec-1"},
        params=None,
        headers={
            "X-Ing-Securityprocessid": "sec-1",
            "X-XSRF-TOKEN": "xsrf-value",
        },
    )


@pytest.mark.asyncio
async def test_confirm_sca_omits_missing_xsrf_token():
    client = INGAPIClient()
    client._genoma_session = _session(headers={"Cookie": "JSESSIONID=abc"})

    await client.confirm_sca("sec-1")

    assert client._genoma_session.request.await_args.kwargs["headers"] == {
        "X-Ing-Securityprocessid": "sec-1"
    }


@pytest.mark.asyncio
async def test_synchronize_access_token_replaces_api_bearer():
    client = INGAPIClient()
    client._api_session = _session(
        headers={"Authorization": "Bearer old-token"},
        response={"accessTokens": [{"accessToken": "new-token"}]},
    )

    assert await client.synchronize_access_token() is True
    assert client._api_session.headers["Authorization"] == "Bearer new-token"
    assert (
        client._api_session.request.await_args.args[1]
        == "https://api.ing.ingdirect.es/saf/tpa/accesstoken/synchronize"
    )


@pytest.mark.asyncio
async def test_synchronize_access_token_keeps_bearer_without_new_token():
    client = INGAPIClient()
    client._api_session = _session(
        headers={"Authorization": "Bearer old-token"}, response={"accessTokens": []}
    )

    assert await client.synchronize_access_token() is False
    assert client._api_session.headers["Authorization"] == "Bearer old-token"
