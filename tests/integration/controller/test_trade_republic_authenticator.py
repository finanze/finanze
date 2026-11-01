import json
from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from dateutil.tz import tzlocal

from domain.entity_account import EntityAccount
from domain.global_position import GlobalPosition
from domain.native_entities import TRADE_REPUBLIC
from domain.status import FFStatus
from infrastructure.client.entity.financial.tr.trade_republic_fetcher import (
    TradeRepublicFetcher,
)
from infrastructure.client.http.http_session import HttpSession

LOGIN_URL = "/api/v1/entities/login"
FETCH_URL = "/api/v1/data/fetch/financial"
PROCESS_ID = "test-process"
PHONE = "+490000000"
PASSWORD = "0000"
WAF_TOKEN = "test-waf"


@pytest_asyncio.fixture
async def trade_republic_flow(monkeypatch, feature_flag_port, entity_fetchers):
    state = {"verified": False}
    calls = []

    async def respond(request):
        calls.append(request)
        path = request.url.path
        if request.method == "POST" and path == "/api/v2/auth/web/login":
            return httpx.Response(
                200,
                json={"processId": PROCESS_ID},
                headers={"set-cookie": "login_session=first-session; Path=/; Secure"},
            )
        if request.method == "GET" and path.endswith(f"/processes/{PROCESS_ID}"):
            assert "login_session=first-session" in request.headers.get("cookie", "")
            if not state["verified"]:
                return httpx.Response(
                    200,
                    json={
                        "status": "PENDING",
                        "requiredAction": "AUTHENTICATOR_VERIFICATION",
                        "expiresAt": "2099-12-31T23:59:59Z",
                    },
                )
            return httpx.Response(
                200,
                json={"status": "CONFIRMED"},
                headers={"set-cookie": "tr_session=confirmed-session; Path=/; Secure"},
            )
        if request.method == "POST" and path.endswith("/authenticator-verification"):
            assert "login_session=first-session" in request.headers.get("cookie", "")
            if json.loads(request.content)["code"] != "003456":
                return httpx.Response(
                    400,
                    json={
                        "errors": [
                            {
                                "errorCode": "VALIDATION_CODE_INVALID",
                                "errorMessage": "Invalid code",
                            }
                        ]
                    },
                )
            state["verified"] = True
            return httpx.Response(200, json={})
        raise AssertionError(f"Unexpected mocked Trade Republic request: {path}")

    http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(
        "infrastructure.client.entity.financial.tr.api.new_http_session",
        lambda: HttpSession(http),
    )
    feature_flag_port.get_all.return_value = {"TR_V2_AUTH_API": FFStatus.ON}
    fetcher = TradeRepublicFetcher()
    fetcher._client._fetch_app_version = AsyncMock(return_value="15.7.0")
    entity_fetchers[TRADE_REPUBLIC] = fetcher
    yield fetcher, calls
    await http.aclose()


@pytest.mark.asyncio
async def test_authenticator_login_persists_only_after_approval(
    client,
    trade_republic_flow,
    credentials_port,
    sessions_port,
    entity_account_port,
):
    _, calls = trade_republic_flow
    entity_account_port.get_by_entity_id.return_value = []
    credentials = {"phone": PHONE, "password": PASSWORD}
    initial = {
        "entity": str(TRADE_REPUBLIC.id),
        "credentials": {**credentials, "awsWafToken": WAF_TOKEN},
    }

    started = await (await client.post(LOGIN_URL, json=initial)).get_json()
    assert started["code"] == "CODE_REQUESTED"
    assert started["confirmationType"] == "IN_APP"

    pending = {**initial, "credentials": credentials, "processId": PROCESS_ID}
    required = await (await client.post(LOGIN_URL, json=pending)).get_json()
    assert required["confirmationType"] == "AUTHENTICATOR"
    assert required["details"]["pinLength"] == 6
    credentials_port.save.assert_not_awaited()
    sessions_port.save.assert_not_awaited()

    invalid = await (
        await client.post(LOGIN_URL, json={**pending, "code": "999999"})
    ).get_json()
    assert invalid["code"] == "INVALID_CODE"
    credentials_port.save.assert_not_awaited()

    verified = await (
        await client.post(LOGIN_URL, json={**pending, "code": "003456"})
    ).get_json()
    assert verified["confirmationType"] == "IN_APP"
    sessions_port.save.assert_not_awaited()

    completed = await (await client.post(LOGIN_URL, json=pending)).get_json()
    assert completed["code"] == "CREATED"
    saved_credentials = credentials_port.save.await_args.args[2]
    saved_session = sessions_port.save.await_args.args[2]
    assert saved_credentials == credentials
    assert saved_session.payload["waf_token"] == WAF_TOKEN
    assert any(
        cookie["name"] == "tr_session" and cookie["value"] == "confirmed-session"
        for cookie in saved_session.payload["cookies"]
    )
    assert [request.method for request in calls] == [
        "POST",
        "GET",
        "POST",
        "POST",
        "GET",
    ]


@pytest.mark.asyncio
async def test_authenticator_relogin_continues_fetch(
    client,
    trade_republic_flow,
    credentials_port,
    sessions_port,
    last_fetches_port,
    entity_account_port,
):
    fetcher, _ = trade_republic_flow
    account_id = uuid4()
    entity_account_port.get_by_id.return_value = EntityAccount(
        id=account_id,
        entity_id=TRADE_REPUBLIC.id,
        created_at=datetime.now(tzlocal()),
    )
    credentials_port.get.side_effect = lambda *_: {
        "phone": PHONE,
        "password": PASSWORD,
    }
    sessions_port.get.return_value = None
    last_fetches_port.get_by_entity_account_id.return_value = []
    fetcher.global_position = AsyncMock(
        return_value=GlobalPosition(id=uuid4(), entity=TRADE_REPUBLIC, products={})
    )
    payload = {"entityAccountId": str(account_id), "features": ["POSITION"]}

    started = await (
        await client.post(
            FETCH_URL, json={**payload, "credentials": {"awsWafToken": WAF_TOKEN}}
        )
    ).get_json()
    assert started["confirmationType"] == "IN_APP"
    pending = {**payload, "processId": PROCESS_ID}

    required = await (await client.post(FETCH_URL, json=pending)).get_json()
    assert required["confirmationType"] == "AUTHENTICATOR"
    assert required["details"]["pinLength"] == 6

    verified = await (
        await client.post(FETCH_URL, json={**pending, "code": "003456"})
    ).get_json()
    assert verified["confirmationType"] == "IN_APP"

    completed = await (await client.post(FETCH_URL, json=pending)).get_json()
    assert completed["code"] == "COMPLETED"
    assert sessions_port.save.await_args.args[2].payload["waf_token"] == WAF_TOKEN
    fetcher.global_position.assert_awaited_once()
