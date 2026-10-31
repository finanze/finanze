from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from dateutil.tz import tzlocal

from domain.entity_account import EntityAccount
from domain.entity_login import EntitySession
from domain.global_position import GlobalPosition
from domain.native_entities import TRADE_REPUBLIC
from domain.status import FFStatus
from infrastructure.client.entity.financial.tr.trade_republic_fetcher import (
    TradeRepublicFetcher,
)
from infrastructure.client.http.http_session import HttpSession

FETCH_URL = "/api/v1/data/fetch/financial"
PROCESS_ID = "v1-process"
WAF_TOKEN = "new-waf"


@pytest.mark.asyncio
async def test_expired_session_retries_v1_with_headers_and_continues_fetch(
    client,
    monkeypatch,
    entity_fetchers,
    feature_flag_port,
    credentials_port,
    sessions_port,
    last_fetches_port,
    entity_account_port,
):
    requests = []

    async def respond(request):
        requests.append(request)
        path = request.url.path
        if request.method == "GET" and path == "/api/v2/auth/account":
            return httpx.Response(401, json={"errors": [{"errorCode": "UNAUTHORIZED"}]})
        if request.method == "POST" and path == "/api/v1/auth/web/login":
            if "x-tr-device-info" not in request.headers:
                return httpx.Response(
                    400,
                    json={"errors": [{"errorCode": "MISSING_REQUIRED_HEADER"}]},
                )
            return httpx.Response(
                200,
                json={"processId": PROCESS_ID, "countdownInSeconds": 4},
                headers={"set-cookie": "login_session=first-session; Path=/; Secure"},
            )
        if request.method == "POST" and path.endswith(f"/{PROCESS_ID}/9999"):
            return httpx.Response(
                400, json={"errors": [{"errorCode": "VALIDATION_CODE_INVALID"}]}
            )
        if request.method == "POST" and path.endswith(f"/{PROCESS_ID}/0345"):
            return httpx.Response(
                200,
                json={},
                headers={"set-cookie": "tr_session=confirmed; Path=/; Secure"},
            )
        raise AssertionError(f"Unexpected mocked Trade Republic request: {path}")

    http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(
        "infrastructure.client.entity.financial.tr.api.new_http_session",
        lambda: HttpSession(http),
    )
    feature_flag_port.get_all.return_value = {"TR_V2_AUTH_API": FFStatus.OFF}
    fetcher = TradeRepublicFetcher()
    fetcher._client._fetch_app_version = AsyncMock(return_value="2.2644.24")
    fetcher.global_position = AsyncMock(
        return_value=GlobalPosition(id=uuid4(), entity=TRADE_REPUBLIC, products={})
    )
    entity_fetchers[TRADE_REPUBLIC] = fetcher
    account_id = uuid4()
    entity_account_port.get_by_id.return_value = EntityAccount(
        id=account_id,
        entity_id=TRADE_REPUBLIC.id,
        created_at=datetime.now(tzlocal()),
    )
    credentials_port.get.side_effect = lambda *_: {
        "phone": "+490000000",
        "password": "0000",
    }
    sessions_port.get.return_value = EntitySession(
        creation=datetime.now(tzlocal()),
        expiration=None,
        payload={"cookies": [], "waf_token": "old-waf"},
    )
    last_fetches_port.get_by_entity_account_id.return_value = []
    payload = {"entityAccountId": str(account_id), "features": ["POSITION"]}

    try:
        started = await (
            await client.post(
                FETCH_URL, json={**payload, "credentials": {"awsWafToken": WAF_TOKEN}}
            )
        ).get_json()
        assert started["code"] == "CODE_REQUESTED"
        assert started["details"]["processId"] == PROCESS_ID

        invalid = await (
            await client.post(
                FETCH_URL,
                json={**payload, "processId": PROCESS_ID, "code": "9999"},
            )
        ).get_json()
        assert invalid["code"] == "INVALID_CODE"
        sessions_port.save.assert_not_awaited()

        completed = await (
            await client.post(
                FETCH_URL,
                json={**payload, "processId": PROCESS_ID, "code": "0345"},
            )
        ).get_json()

        assert completed["code"] == "COMPLETED"
        assert [request.url.path for request in requests] == [
            "/api/v2/auth/account",
            "/api/v1/auth/web/login",
            "/api/v1/auth/web/login",
            f"/api/v1/auth/web/login/{PROCESS_ID}/9999",
            f"/api/v1/auth/web/login/{PROCESS_ID}/0345",
        ]
        assert "x-tr-device-info" not in requests[1].headers
        assert requests[2].headers["x-tr-app-version"] == "2.2644.24"
        assert requests[2].headers["x-tr-platform"] == "web"
        assert requests[2].headers["accept-language"] == "en"
        assert (
            requests[4].headers["x-tr-device-info"]
            == requests[2].headers["x-tr-device-info"]
        )
        assert requests[4].headers["x-aws-waf-token"] == WAF_TOKEN
        assert "login_session=first-session" in requests[4].headers["cookie"]
        assert sessions_port.save.await_args.args[2].payload["waf_token"] == WAF_TOKEN
        fetcher._client._fetch_app_version.assert_awaited_once()
        fetcher.global_position.assert_awaited_once()
    finally:
        await http.aclose()
