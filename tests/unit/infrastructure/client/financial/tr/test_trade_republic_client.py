import base64
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dateutil.tz import tzlocal

from domain.entity_login import (
    EntityLoginResult,
    EntitySession,
    LoginConfirmationType,
    LoginOptions,
    LoginResultCode,
)
from infrastructure.client.entity.financial.tr.trade_republic_client import (
    TradeRepublicClient,
)

API_CLASS = (
    "infrastructure.client.entity.financial.tr.trade_republic_client.TradeRepublicApi"
)


def _make_response(status=200, json_data=None):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.raise_for_status = MagicMock()
    resp.text = ""
    return resp


def _make_mock_api():
    api = MagicMock()
    api._host = "https://api.traderepublic.com"
    api.phone_no = "+49123456789"
    api.pin = "1234"
    api._websession = MagicMock()
    api._websession.cookies = MagicMock()
    api._websession.cookies.jar = []
    api._websession.headers = {}
    api._weblogin = False
    api._process_id = None
    api.settings = AsyncMock()
    return api


def _make_client(use_v2=True):
    client = TradeRepublicClient(use_v2=use_v2)
    client._tr_api = _make_mock_api()
    client._stable_device_id = "a" * 128
    return client


class TestInitiateWebloginV2:
    @pytest.mark.asyncio
    async def test_returns_process_id_on_success(self):
        client = _make_client()
        resp = _make_response(200, {"processId": "proc-123", "countdownInSeconds": 30})
        client._tr_api._websession.post = AsyncMock(return_value=resp)

        result = await client._initiate_weblogin_v2()

        assert result == "proc-123"
        assert client._tr_api._process_id == "proc-123"
        call_kwargs = client._tr_api._websession.post.call_args
        headers = call_kwargs.kwargs["headers"]
        assert headers["x-tr-platform"] == "web"
        assert headers["x-tr-app-version"] == "15.7.0"
        assert "x-tr-device-info" in headers

    @pytest.mark.asyncio
    async def test_returns_cooldown_on_too_many_requests(self):
        client = _make_client()
        resp = _make_response(
            429,
            {
                "errors": [
                    {
                        "errorCode": "TOO_MANY_REQUESTS",
                        "meta": {"nextAttemptInSeconds": 120},
                    }
                ]
            },
        )
        client._tr_api._websession.post = AsyncMock(return_value=resp)

        result = await client._initiate_weblogin_v2()

        assert isinstance(result, EntityLoginResult)
        assert result.code == LoginResultCode.COOLDOWN
        assert result.details["wait"] == 120

    @pytest.mark.asyncio
    async def test_returns_error_when_no_process_id(self):
        client = _make_client()
        resp = _make_response(200, {})
        client._tr_api._websession.post = AsyncMock(return_value=resp)

        result = await client._initiate_weblogin_v2()

        assert isinstance(result, EntityLoginResult)
        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "processId" in result.message


class TestPollWebloginV2:
    @pytest.mark.asyncio
    async def test_returns_none_on_confirmed(self):
        client = _make_client()
        resp = _make_response(200, {"status": "CONFIRMED", "expiresAt": None})
        client._tr_api._websession.get = AsyncMock(return_value=resp)

        result = await client._poll_weblogin_v2("proc-123")

        assert result is None
        call_kwargs = client._tr_api._websession.get.call_args
        headers = call_kwargs.kwargs["headers"]
        assert headers["x-tr-platform"] == "web"
        assert "x-tr-device-info" in headers

    @pytest.mark.asyncio
    async def test_polls_until_confirmed(self):
        client = _make_client()
        pending = _make_response(
            200, {"status": "PENDING", "expiresAt": "2099-12-31T23:59:59.000000Z"}
        )
        confirmed = _make_response(200, {"status": "CONFIRMED", "expiresAt": None})
        client._tr_api._websession.get = AsyncMock(side_effect=[pending, confirmed])

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client._poll_weblogin_v2("proc-123")

        assert result is None
        assert client._tr_api._websession.get.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_error_on_cancel(self):
        client = _make_client()
        pending = _make_response(
            200, {"status": "PENDING", "expiresAt": "2099-12-31T23:59:59.000000Z"}
        )
        client._tr_api._websession.get = AsyncMock(return_value=pending)
        client._cancel_event.set()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client._poll_weblogin_v2("proc-123")

        assert isinstance(result, EntityLoginResult)
        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "cancelled" in result.message.lower()

    @pytest.mark.asyncio
    async def test_returns_error_on_timeout(self):
        client = _make_client()
        expired_time = "2020-01-01T00:00:00.000000Z"
        pending = _make_response(200, {"status": "PENDING", "expiresAt": expired_time})
        client._tr_api._websession.get = AsyncMock(return_value=pending)

        result = await client._poll_weblogin_v2("proc-123")

        assert isinstance(result, EntityLoginResult)
        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "timed out" in result.message.lower()

        assert isinstance(result, EntityLoginResult)
        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "timed out" in result.message.lower()


class TestCompleteLogin:
    @pytest.mark.asyncio
    async def test_returns_created_on_confirmed(self):
        client = _make_client()
        resp = _make_response(200, {"status": "CONFIRMED", "expiresAt": None})
        client._tr_api._websession.get = AsyncMock(return_value=resp)

        result = await client.complete_login("proc-123", "waf-token-abc")

        assert result.code == LoginResultCode.CREATED
        assert result.session is not None
        assert result.session.payload["waf_token"] == "waf-token-abc"
        assert result.session.payload["stable_device_id"] is not None
        assert client._tr_api._weblogin is True

    @pytest.mark.asyncio
    async def test_returns_error_when_no_api(self):
        client = TradeRepublicClient(use_v2=True)

        result = await client.complete_login("proc-123", "waf-token")

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "No login in progress" in result.message


class TestCancelLogin:
    def test_sets_cancel_event(self):
        client = _make_client()

        assert not client._cancel_event.is_set()
        client.cancel_login()
        assert client._cancel_event.is_set()


class TestLoginV2Flow:
    @pytest.mark.asyncio
    async def test_login_with_waf_token_uses_v2(self):
        mock_api = _make_mock_api()
        resp = _make_response(200, {"processId": "proc-v2"})
        mock_api._websession.post = AsyncMock(return_value=resp)

        with patch(API_CLASS, return_value=mock_api):
            client = TradeRepublicClient(use_v2=True)
            result = await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
                waf_token="waf-abc",
            )

        assert result.code == LoginResultCode.CODE_REQUESTED
        assert result.confirmation_type == LoginConfirmationType.IN_APP
        assert result.process_id == "proc-v2"

    @pytest.mark.asyncio
    async def test_login_with_waf_token_uses_v1_when_flag_off(self):
        mock_api = _make_mock_api()
        resp = _make_response(200, {"processId": "proc-v1", "countdownInSeconds": 10})
        mock_api._websession.post = AsyncMock(return_value=resp)

        with patch(API_CLASS, return_value=mock_api):
            client = TradeRepublicClient(use_v2=False)
            result = await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
                waf_token="waf-abc",
            )

        assert result.code == LoginResultCode.CODE_REQUESTED
        assert result.confirmation_type is None
        assert result.process_id == "proc-v1"
        assert result.details["wait"] == 11

    @pytest.mark.asyncio
    async def test_login_without_waf_token_returns_manual_login(self):
        mock_api = _make_mock_api()

        with patch(API_CLASS, return_value=mock_api):
            client = TradeRepublicClient(use_v2=True)
            result = await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
            )

        assert result.code == LoginResultCode.MANUAL_LOGIN

    @pytest.mark.asyncio
    async def test_login_rejects_phone_without_prefix(self):
        client = TradeRepublicClient(use_v2=True)
        result = await client.login(
            phone="49123456789",
            pin="1234",
            login_options=LoginOptions(),
            waf_token="waf-abc",
        )

        assert result.code == LoginResultCode.INVALID_CREDENTIALS
        assert "international prefix" in result.message

    @pytest.mark.asyncio
    async def test_login_with_code_and_process_id_uses_v1_completion(self):
        mock_api = _make_mock_api()
        mock_api.complete_weblogin = AsyncMock()

        with patch(API_CLASS, return_value=mock_api):
            client = TradeRepublicClient(use_v2=True)
            result = await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
                waf_token="waf-abc",
                process_id="proc-123",
                code="123456",
            )

        assert result.code == LoginResultCode.CREATED
        mock_api.complete_weblogin.assert_called_once_with("123456")

    @pytest.mark.asyncio
    async def test_login_resumes_existing_session(self):
        mock_api = _make_mock_api()
        mock_api.settings = AsyncMock(return_value={})
        mock_api._websession.clear_cookies = MagicMock()
        mock_api._websession.set_cookie = MagicMock()

        session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload={"cookies": [], "waf_token": "old-waf"},
        )

        with patch(API_CLASS, return_value=mock_api):
            client = TradeRepublicClient(use_v2=True)
            result = await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
                session=session,
            )

        assert result.code == LoginResultCode.RESUMED


class TestDeviceInfo:
    def test_generate_stable_device_id_returns_128_hex_chars(self):
        device_id = TradeRepublicClient._generate_stable_device_id()

        assert len(device_id) == 128
        assert all(c in "0123456789abcdef" for c in device_id)

    def test_generate_stable_device_id_is_unique(self):
        id1 = TradeRepublicClient._generate_stable_device_id()
        id2 = TradeRepublicClient._generate_stable_device_id()

        assert id1 != id2

    def test_build_device_info_header_is_valid_base64_json(self):
        client = _make_client()

        header = client._build_device_info_header()

        decoded = json.loads(base64.b64decode(header))
        assert decoded["stableDeviceId"] == "a" * 128
        assert decoded["model"] == "Apple Macintosh"
        assert decoded["browser"] == "Firefox"
        assert decoded["os"] == "Mac OS"
        assert "preferredLanguages" in decoded

    def test_get_v2_headers_includes_device_info(self):
        client = _make_client()

        headers = client._get_v2_headers()

        assert headers["x-tr-platform"] == "web"
        assert headers["x-tr-app-version"] == "15.7.0"
        assert "x-tr-device-info" in headers

    def test_stable_device_id_persists_in_session_export(self):
        client = _make_client()
        client._stable_device_id = "b" * 128

        payload = client._export_session("waf-123")

        assert payload["stable_device_id"] == "b" * 128

    def test_stable_device_id_restored_from_session(self):
        client = _make_client()
        client._stable_device_id = None

        session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload={
                "cookies": [],
                "waf_token": "waf-123",
                "stable_device_id": "c" * 128,
            },
        )
        client._inject_session(session)

        assert client._stable_device_id == "c" * 128

    @pytest.mark.asyncio
    async def test_login_generates_device_id_when_missing(self):
        mock_api = _make_mock_api()
        resp = _make_response(200, {"processId": "proc-v2"})
        mock_api._websession.post = AsyncMock(return_value=resp)

        with patch(API_CLASS, return_value=mock_api):
            client = TradeRepublicClient(use_v2=True)
            assert client._stable_device_id is None
            await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
                waf_token="waf-abc",
            )

        assert client._stable_device_id is not None
        assert len(client._stable_device_id) == 128

    @pytest.mark.asyncio
    async def test_login_preserves_device_id_from_session(self):
        mock_api = _make_mock_api()
        mock_api.settings = AsyncMock(return_value={})
        mock_api._websession.clear_cookies = MagicMock()
        mock_api._websession.set_cookie = MagicMock()
        original_id = "d" * 128

        session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload={
                "cookies": [],
                "waf_token": "old-waf",
                "stable_device_id": original_id,
            },
        )

        with patch(API_CLASS, return_value=mock_api):
            client = TradeRepublicClient(use_v2=True)
            await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
                session=session,
            )

        assert client._stable_device_id == original_id
