import base64
import json
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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
from infrastructure.client.entity.financial.tr.api import (
    TradeRepublicApi,
    TradeRepublicError,
)
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.client.http.http_session import HttpSession

API_CLASS = (
    "infrastructure.client.entity.financial.tr.trade_republic_client.TradeRepublicApi"
)


def _make_response(status=200, json_data=None):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.raise_for_status = MagicMock()
    resp.text = AsyncMock(return_value=json.dumps(json_data or {}))
    return resp


def _http_response(status, json_data=None, content=None):
    kwargs = {"content": content} if content is not None else {"json": json_data}
    request = httpx.Request("POST", "https://api.traderepublic.com/login")
    return HttpResponse(httpx.Response(status, request=request, **kwargs))


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
    api.has_websocket_auth = AsyncMock(return_value=True)
    return api


def _make_client():
    client = TradeRepublicClient()
    client._tr_api = _make_mock_api()
    client._tr_api._process_id = "proc-123"
    client._stable_device_id = "a" * 128
    client._fetch_app_version = AsyncMock(return_value="15.7.0")
    return client


class TestInitiateWebloginV2:
    @pytest.mark.asyncio
    async def test_rejects_response_from_a_replaced_login_session(self):
        client = _make_client()
        replacement = _make_mock_api()

        async def respond(*args, **kwargs):
            client._tr_api = replacement
            return _make_response(200, {"processId": "old-process"})

        client._tr_api._websession.post = AsyncMock(side_effect=respond)

        result = await client._initiate_weblogin_v2()

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert replacement._process_id is None

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

    @pytest.mark.asyncio
    async def test_returns_error_for_null_process_id(self):
        client = _make_client()
        client._tr_api._websession.post = AsyncMock(
            return_value=_make_response(200, {"processId": None})
        )

        result = await client._initiate_weblogin_v2()

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "processId" in result.message


class TestPollWebloginV2:
    @pytest.mark.asyncio
    async def test_requests_authenticator_before_waiting_for_approval(self):
        client = _make_client()
        pending = _make_response(
            200,
            {
                "status": "PENDING",
                "requiredAction": "AUTHENTICATOR_VERIFICATION",
                "expiresAt": "2099-12-31T23:59:59Z",
            },
        )
        client._tr_api._websession.get = AsyncMock(return_value=pending)

        with patch(
            "asyncio.sleep", new=AsyncMock(side_effect=lambda _: client.cancel_login())
        ):
            result = await client._poll_weblogin_v2("proc-123")

        assert result.code == LoginResultCode.CODE_REQUESTED
        assert result.confirmation_type == "AUTHENTICATOR"
        assert result.process_id == "proc-123"
        assert result.details["pinLength"] == 6

    @pytest.mark.asyncio
    async def test_returns_none_on_completed(self):
        client = _make_client()
        completed = _make_response(200, {"status": "COMPLETED"})
        client._tr_api._websession.get = AsyncMock(return_value=completed)

        with patch(
            "asyncio.sleep", new=AsyncMock(side_effect=lambda _: client.cancel_login())
        ):
            result = await client._poll_weblogin_v2("proc-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_missing_expiry_has_a_bounded_timeout(self):
        client = _make_client()
        client.IN_APP_TIMEOUT_SECONDS = 0
        client._tr_api._websession.get = AsyncMock(
            return_value=_make_response(200, {"status": "PENDING"})
        )

        with patch(
            "asyncio.sleep", new=AsyncMock(side_effect=lambda _: client.cancel_login())
        ):
            result = await client._poll_weblogin_v2("proc-123")

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "timed out" in result.message.lower()

    @pytest.mark.asyncio
    async def test_verified_authenticator_does_not_prompt_twice(self):
        client = _make_client()
        client._v2_authenticator_verified = True
        client._tr_api._websession.get = AsyncMock(
            side_effect=[
                _make_response(
                    200,
                    {
                        "status": "PENDING",
                        "requiredAction": "AUTHENTICATOR_VERIFICATION",
                    },
                ),
                _make_response(200, {"status": "CONFIRMED"}),
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client._poll_weblogin_v2("proc-123")

        assert result is None
        assert client._tr_api._websession.get.await_count == 2

    @pytest.mark.asyncio
    async def test_reports_unknown_process_status(self):
        client = _make_client()
        client._tr_api._websession.get = AsyncMock(
            return_value=_make_response(
                200,
                {
                    "status": "REJECTED",
                    "requiredAction": "AUTHENTICATOR_VERIFICATION",
                },
            )
        )

        result = await client._poll_weblogin_v2("proc-123")

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "status" in result.message.lower()

    @pytest.mark.asyncio
    async def test_zero_timestamp_is_treated_as_expired(self):
        client = _make_client()
        client._tr_api._websession.get = AsyncMock(
            return_value=_make_response(200, {"status": "PENDING", "expiresAt": 0})
        )

        result = await client._poll_weblogin_v2("proc-123")

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "timed out" in result.message.lower()

    @pytest.mark.asyncio
    async def test_cancellation_during_poll_does_not_create_a_session(self):
        client = _make_client()

        async def confirm_after_cancellation(*args, **kwargs):
            client.cancel_login()
            return _make_response(200, {"status": "CONFIRMED"})

        client._tr_api._websession.get = AsyncMock(
            side_effect=confirm_after_cancellation
        )

        result = await client.complete_login("proc-123", "waf")

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "cancelled" in result.message.lower()
        assert result.session is None

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
    async def test_rejects_a_different_process_without_sending_the_code(self):
        client = _make_client()
        client._v2_authenticator_required = True
        client._tr_api._websession.post = AsyncMock()

        result = await client.complete_login("another-process", "waf", code="003456")

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        client._tr_api._websession.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cancelled_authenticator_does_not_submit_the_code(self):
        client = _make_client()
        client._v2_authenticator_required = True
        client._tr_api._websession.post = AsyncMock()
        client.cancel_login()

        result = await client.complete_login("proc-123", "waf", code="003456")

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "cancelled" in result.message.lower()
        client._tr_api._websession.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_submits_authenticator_code_using_existing_session(self):
        client = _make_client()
        client._tr_api._process_id = "proc-123"
        client._v2_authenticator_required = True
        api = client._tr_api
        client._tr_api._websession.post = AsyncMock(return_value=_make_response(200))

        result = await client.complete_login("proc-123", "waf-token", code="003456")

        assert result.code == LoginResultCode.CODE_REQUESTED
        assert result.confirmation_type == LoginConfirmationType.IN_APP
        assert result.process_id == "proc-123"
        assert client._tr_api is api
        call = api._websession.post.await_args
        assert call.args[0].endswith("/proc-123/authenticator-verification")
        assert call.kwargs["json"] == {"code": "003456"}
        assert call.kwargs["headers"]["x-tr-platform"] == "web"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error_code", ["VALIDATION_CODE_INVALID", "VALIDATION_CODE_ALREADY_USED"]
    )
    async def test_invalid_authenticator_code_is_retryable_and_not_logged(
        self, caplog, error_code
    ):
        client = _make_client()
        client._tr_api._process_id = "proc-secret"
        client._v2_authenticator_required = True
        client._tr_api._websession.headers["x-aws-waf-token"] = "waf-secret"
        client._tr_api._websession.post = AsyncMock(
            return_value=_http_response(
                400,
                {
                    "errors": [
                        {
                            "errorCode": error_code,
                            "errorMessage": "Invalid code 003456 for +49123456789",
                        }
                    ]
                },
            )
        )

        with caplog.at_level(logging.ERROR):
            result = await client.complete_login(
                "proc-secret", "waf-secret", code="003456"
            )

        assert result.code == LoginResultCode.INVALID_CODE
        assert error_code in caplog.text
        assert "003456" not in caplog.text
        assert "+49123456789" not in caplog.text
        assert "proc-secret" not in caplog.text
        assert "waf-secret" not in caplog.text

    @pytest.mark.asyncio
    async def test_returns_created_on_confirmed(self):
        client = _make_client()
        client._tr_api._process_id = "proc-123"
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
        client = TradeRepublicClient()

        result = await client.complete_login("proc-123", "waf-token")

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "No login in progress" in result.message


class TestLoginErrorLogging:
    @pytest.mark.asyncio
    async def test_httpx_logs_hide_authentication_process_and_code(self, caplog):
        async def respond(request):
            return httpx.Response(200, json={})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = _make_client()
            client._tr_api._websession = HttpSession(http)
            client._tr_api._process_id = "private-process"
            client._v2_authenticator_required = True

            with caplog.at_level(logging.INFO, logger="httpx"):
                await client.complete_login("private-process", "waf", code="003456")
                client._tr_api._process_id = "v1-private-process"
                await TradeRepublicApi.complete_weblogin(client._tr_api, "123456")

        assert "HTTP Request" in caplog.text
        assert "[REDACTED]" in caplog.text
        assert "private-process" not in caplog.text
        assert "003456" not in caplog.text
        assert "123456" not in caplog.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize("version", ["v1", "v2"])
    async def test_logs_redacted_trade_republic_error_response(self, caplog, version):
        client = _make_client()
        client._tr_api._process_id = "proc-secret"
        client._tr_api._websession.headers["x-aws-waf-token"] = "waf-secret"
        client._tr_api._websession.post = AsyncMock(
            return_value=_http_response(
                400,
                {
                    "errors": [
                        {
                            "errorCode": "NUMBER_INVALID",
                            "errorMessage": "Invalid +49123456789 PIN 1234",
                            "meta": {
                                "nextAttemptInSeconds": 60,
                                "field": "phoneNumber",
                                "reason": "INVALID_FORMAT",
                                "headerName": "x-tr-device-info",
                                "missingHeaders": ["x-tr-platform", "x-tr-app-version"],
                                "token": "waf-secret",
                            },
                        }
                    ],
                    "processId": "proc-secret",
                },
            )
        )

        with caplog.at_level(logging.ERROR):
            result = await getattr(client, f"_login_{version}")()

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "NUMBER_INVALID" in caplog.text
        assert "Invalid" in caplog.text
        assert "nextAttemptInSeconds" in caplog.text
        assert "INVALID_FORMAT" in caplog.text
        assert "phoneNumber" in caplog.text
        assert "x-tr-device-info" in caplog.text
        assert "x-tr-platform" in caplog.text
        assert "+49123456789" not in caplog.text
        assert "1234" not in caplog.text
        assert "proc-secret" not in caplog.text
        assert "waf-secret" not in caplog.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize("version", ["v1", "v2"])
    async def test_logs_invalid_error_shape_even_when_process_id_is_present(
        self, caplog, version
    ):
        client = _make_client()
        client._tr_api._websession.post = AsyncMock(
            return_value=_http_response(
                200,
                {
                    "processId": "unexpected-process",
                    "errors": [{"meta": {"field": "phoneNumber"}}],
                },
            )
        )

        with caplog.at_level(logging.ERROR):
            result = await getattr(client, f"_login_{version}")()

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert "phoneNumber" in caplog.text
        assert "unexpected-process" not in caplog.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize("version", ["v1", "v2"])
    async def test_logs_empty_waf_response_before_handling_status(
        self, caplog, version
    ):
        client = _make_client()
        client._tr_api._websession.post = AsyncMock(
            return_value=_http_response(405, content=b"")
        )

        with caplog.at_level(logging.ERROR):
            result = await getattr(client, f"_login_{version}")()

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert result.message == "Invalid challenge token"
        assert "405" in caplog.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize("version", ["v1", "v2"])
    async def test_logs_non_json_rate_limit_without_its_sensitive_body(
        self, caplog, version
    ):
        client = _make_client()
        client._tr_api._websession.post = AsyncMock(
            return_value=_http_response(429, content=b"secret response contents")
        )

        with caplog.at_level(logging.ERROR):
            result = await getattr(client, f"_login_{version}")()

        assert result.code == LoginResultCode.COOLDOWN
        assert result.details["wait"] == 60
        assert "429" in caplog.text
        assert "secret response contents" not in caplog.text

    @pytest.mark.asyncio
    async def test_logs_rejected_challenge_response(self, caplog):
        client = _make_client()
        client._tr_api._websession.post = AsyncMock(
            return_value=_http_response(
                403,
                {
                    "errors": [
                        {"errorCode": "CHALLENGE_REJECTED", "errorMessage": "WAF"}
                    ]
                },
            )
        )

        with caplog.at_level(logging.ERROR):
            result = await client._login_v2()

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert result.message == "Invalid challenge token"
        assert "CHALLENGE_REJECTED" in caplog.text


class TestWebsocketErrors:
    @pytest.mark.asyncio
    async def test_authentication_error_remains_trade_republic_error(self):
        api = TradeRepublicApi("+49123456789", "1234")
        api._ws = AsyncMock()
        api._ws.close_code = None
        api._ws.recv = AsyncMock(
            return_value=(
                '1 E {"errors":[{"errorCode":"AUTHENTICATION_ERROR",'
                '"errorMessage":"No auth token"}]}'
            )
        )
        api.subscriptions["1"] = {"type": "compactPortfolioByType"}

        with pytest.raises(TradeRepublicError) as error:
            await api.recv()

        assert error.value.error["errors"][0]["errorCode"] == "AUTHENTICATION_ERROR"
        api._ws.send.assert_awaited_once_with("unsub 1")

    @pytest.mark.asyncio
    async def test_non_authentication_error_remains_trade_republic_error(self):
        api = TradeRepublicApi("+49123456789", "1234")
        api._ws = AsyncMock()
        api._ws.close_code = None
        api._ws.recv = AsyncMock(
            return_value=(
                '1 E {"errors":[{"errorCode":"INVALID_REQUEST",'
                '"errorMessage":"Invalid request"}]}'
            )
        )
        api.subscriptions["1"] = {"type": "compactPortfolioByType"}

        with pytest.raises(TradeRepublicError) as error:
            await api.recv()

        assert error.value.subscription == {"type": "compactPortfolioByType"}


class TestCancelLogin:
    def test_sets_cancel_event(self):
        client = _make_client()

        assert not client._cancel_event.is_set()
        client.cancel_login()
        assert client._cancel_event.is_set()


class TestClose:
    @pytest.mark.asyncio
    async def test_close_delegates_to_api_and_nulls_ws(self):
        api = TradeRepublicApi("+49123456789", "1234")
        ws = AsyncMock()
        api._ws = ws
        api.subscriptions["1"] = {"type": "compactPortfolioByType"}
        api._previous_responses["1"] = "cached"

        client = TradeRepublicClient()
        client._tr_api = api

        await client.close()

        ws.close.assert_awaited_once()
        assert api._ws is None
        assert api.subscriptions == {}
        assert api._previous_responses == {}

    @pytest.mark.asyncio
    async def test_close_without_api_is_noop(self):
        client = TradeRepublicClient()

        await client.close()

    @pytest.mark.asyncio
    async def test_close_swallows_api_errors(self):
        client = _make_client()
        client._tr_api.close = AsyncMock(side_effect=RuntimeError("already closed"))

        await client.close()


class TestLoginV2Flow:
    @pytest.mark.asyncio
    async def test_login_with_waf_token_uses_v2(self):
        mock_api = _make_mock_api()
        resp = _make_response(200, {"processId": "proc-v2"})
        mock_api._websession.post = AsyncMock(return_value=resp)

        with patch(API_CLASS, return_value=mock_api):
            client = TradeRepublicClient()
            client._fetch_app_version = AsyncMock(return_value="15.7.0")
            result = await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
                waf_token="waf-abc",
                use_v2=True,
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
            client = TradeRepublicClient()
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
            client = TradeRepublicClient()
            result = await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
            )

        assert result.code == LoginResultCode.MANUAL_LOGIN

    @pytest.mark.asyncio
    async def test_login_rejects_phone_without_prefix(self):
        client = TradeRepublicClient()
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
            client = TradeRepublicClient()
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
            client = TradeRepublicClient()
            result = await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
                session=session,
            )

        assert result.code == LoginResultCode.RESUMED

    @pytest.mark.asyncio
    async def test_login_requires_login_when_session_has_no_websocket_auth(self):
        mock_api = _make_mock_api()
        mock_api.settings = AsyncMock(return_value={})
        mock_api.has_websocket_auth = AsyncMock(return_value=False)
        mock_api._websession.clear_cookies = MagicMock()
        mock_api._websession.set_cookie = MagicMock()

        session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload={"cookies": [], "waf_token": "old-waf"},
        )

        with patch(API_CLASS, return_value=mock_api):
            client = TradeRepublicClient()
            result = await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
                session=session,
            )

        assert result.code == LoginResultCode.LOGIN_REQUIRED
        mock_api.has_websocket_auth.assert_awaited_once()
        mock_api._websession.post.assert_not_called()


class TestV1MissingHeaders:
    @pytest.mark.asyncio
    async def test_confirmation_rejects_mismatched_process_or_credentials(self):
        client = _make_client()
        client._v1_header_process_id = "proc-123"
        client._tr_api.complete_weblogin = AsyncMock()

        with patch(API_CLASS) as factory:
            wrong_process = await client.login(
                "+49123456789",
                "1234",
                LoginOptions(),
                process_id="another-process",
                code="0345",
                waf_token="test-waf",
            )
            wrong_credentials = await client.login(
                "+490000000",
                "1234",
                LoginOptions(),
                process_id="proc-123",
                code="0345",
                waf_token="test-waf",
            )

        assert wrong_process.code == LoginResultCode.UNEXPECTED_ERROR
        assert wrong_credentials.code == LoginResultCode.INVALID_CREDENTIALS
        factory.assert_not_called()
        client._tr_api.complete_weblogin.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_verification_missing_header_is_not_reported_as_invalid_code(self):
        client = _make_client()
        client._v1_header_process_id = "proc-123"
        request = httpx.Request("POST", "https://api.traderepublic.com/login")
        response = httpx.Response(
            400,
            request=request,
            json={"errors": [{"errorCode": "MISSING_REQUIRED_HEADER"}]},
        )
        client._tr_api.complete_weblogin = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "verification failed", request=request, response=response
            )
        )

        result = await client.login(
            "+49123456789",
            "1234",
            LoginOptions(),
            process_id="proc-123",
            code="0345",
        )

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert client._v1_header_process_id == "proc-123"
        client._tr_api.complete_weblogin.assert_awaited_once_with("0345")

    @pytest.mark.asyncio
    async def test_retries_with_device_headers_and_keeps_session_for_confirmation(self):
        requests = []

        async def respond(request):
            requests.append(request)
            if request.url.path == "/api/v1/auth/web/login":
                if len(requests) == 1:
                    return httpx.Response(
                        400,
                        json={"errors": [{"errorCode": "MISSING_REQUIRED_HEADER"}]},
                    )
                return httpx.Response(
                    200,
                    json={"processId": "v1-process", "countdownInSeconds": 4},
                    headers={
                        "set-cookie": "login_session=first-session; Path=/; Secure"
                    },
                )
            assert request.url.path == "/api/v1/auth/web/login/v1-process/0345"
            return httpx.Response(
                200,
                json={},
                headers={"set-cookie": "tr_session=confirmed; Path=/; Secure"},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            with patch(
                "infrastructure.client.entity.financial.tr.api.new_http_session",
                side_effect=lambda: HttpSession(http),
            ) as factory:
                client = TradeRepublicClient()
                client._fetch_app_version = AsyncMock(return_value="2.2644.24")
                started = await client.login(
                    "+490000000",
                    "0000",
                    LoginOptions(),
                    waf_token="test-waf",
                )

                assert started.code == LoginResultCode.CODE_REQUESTED
                assert started.process_id == "v1-process"
                assert started.details["wait"] == 5
                assert "x-tr-device-info" not in requests[0].headers
                assert requests[1].headers["x-tr-platform"] == "web"
                assert requests[1].headers["x-tr-app-version"] == "2.2644.24"
                assert requests[1].headers["x-tr-device-info"]
                assert requests[1].headers["accept-language"] == "en"
                assert requests[0].content == requests[1].content

                completed = await client.login(
                    "+490000000",
                    "0000",
                    LoginOptions(),
                    process_id="v1-process",
                    code="0345",
                )

                assert completed.code == LoginResultCode.CREATED
                assert completed.session.payload["waf_token"] == "test-waf"
                assert (
                    requests[2].headers["x-tr-device-info"]
                    == requests[1].headers["x-tr-device-info"]
                )
                assert "login_session=first-session" in requests[2].headers["cookie"]
                assert factory.call_count == 1

    @pytest.mark.asyncio
    async def test_missing_header_retry_is_limited_to_one_attempt(self):
        client = _make_client()

        def response():
            return _http_response(
                400, {"errors": [{"errorCode": "MISSING_REQUIRED_HEADER"}]}
            )

        client._tr_api._locale = "en"
        client._tr_api._websession.post = AsyncMock(
            side_effect=[response(), response()]
        )

        result = await client._login_v1()

        assert result.code == LoginResultCode.UNEXPECTED_ERROR
        assert client._tr_api._websession.post.await_count == 2
        client._fetch_app_version.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status", "error_code", "expected"),
        [
            (400, "NUMBER_INVALID", LoginResultCode.UNEXPECTED_ERROR),
            (403, "MISSING_REQUIRED_HEADER", LoginResultCode.UNEXPECTED_ERROR),
            (429, "TOO_MANY_REQUESTS", LoginResultCode.COOLDOWN),
        ],
    )
    async def test_other_failures_do_not_trigger_retry(
        self, status, error_code, expected
    ):
        client = _make_client()
        client._tr_api._websession.post = AsyncMock(
            return_value=_http_response(status, {"errors": [{"errorCode": error_code}]})
        )

        result = await client._login_v1()

        assert result.code == expected
        client._tr_api._websession.post.assert_awaited_once()
        client._fetch_app_version.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_successful_v1_login_does_not_fetch_device_headers(self):
        client = _make_client()
        client._tr_api._websession.post = AsyncMock(
            return_value=_make_response(
                200, {"processId": "v1-process", "countdownInSeconds": 4}
            )
        )

        result = await client._login_v1()

        assert result.code == LoginResultCode.CODE_REQUESTED
        client._fetch_app_version.assert_not_awaited()


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

    @pytest.mark.asyncio
    async def test_get_v2_headers_includes_device_info(self):
        client = _make_client()

        headers = await client._get_v2_headers()

        assert headers["x-tr-platform"] == "web"
        assert headers["x-tr-app-version"] == "15.7.0"
        assert "x-tr-device-info" in headers

    @pytest.mark.asyncio
    async def test_fetch_app_version_returns_remote_version(self):
        await TradeRepublicClient._fetch_app_version.cache.clear()
        client = TradeRepublicClient()
        mock_response = MagicMock()
        mock_response.text = AsyncMock(return_value="16.0.0\n")
        mock_response.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_response)

        with patch(
            "infrastructure.client.entity.financial.tr.trade_republic_client.get_http_session",
            return_value=mock_session,
        ):
            version = await client._fetch_app_version()

        assert version == "16.0.0"

    @pytest.mark.asyncio
    async def test_fetch_app_version_returns_default_on_error(self):
        await TradeRepublicClient._fetch_app_version.cache.clear()
        client = TradeRepublicClient()
        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=httpx.HTTPError("connection failed"))

        with patch(
            "infrastructure.client.entity.financial.tr.trade_republic_client.get_http_session",
            return_value=mock_session,
        ):
            version = await client._fetch_app_version()

        assert version == "15.7.0"

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
            client = TradeRepublicClient()
            client._fetch_app_version = AsyncMock(return_value="15.7.0")
            assert client._stable_device_id is None
            await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
                waf_token="waf-abc",
                use_v2=True,
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
            client = TradeRepublicClient()
            await client.login(
                phone="+49123456789",
                pin="1234",
                login_options=LoginOptions(),
                session=session,
            )

        assert client._stable_device_id == original_id
