from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from dateutil.tz import tzlocal
from domain.exception.exceptions import IntegrationSetupError, IntegrationSetupErrorCode
from domain.external_integration import DeviceAuthorizationStatus
from infrastructure.client.ai.github_copilot.github_device_flow import (
    ACCESS_TOKEN_URL,
    DEVICE_CODE_URL,
    DEVICE_GRANT_TYPE,
    VERIFICATION_URI,
    GitHubDeviceFlow,
)
from infrastructure.client.http.http_response import HttpResponse

CLIENT_ID = "Iv1.client"
SCOPE = "read:user"
DEVICE_CODE = "device-code-secret"
DEVICE_RESPONSE = {
    "device_code": DEVICE_CODE,
    "user_code": "ABCD-1234",
    "verification_uri": VERIFICATION_URI,
    "expires_in": 900,
    "interval": 5,
}


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float):
        self.now += seconds


def _response(status: int, body) -> HttpResponse:
    if isinstance(body, (dict, list)):
        return HttpResponse(httpx.Response(status, json=body))
    return HttpResponse(httpx.Response(status, text=body))


def _flow(*responses) -> tuple[GitHubDeviceFlow, AsyncMock, Clock]:
    session = AsyncMock()
    session.post.side_effect = list(responses)
    clock = Clock()
    return GitHubDeviceFlow(CLIENT_ID, SCOPE, session, clock), session, clock


async def _started(*poll_responses):
    flow, session, clock = _flow(_response(200, DEVICE_RESPONSE), *poll_responses)
    authorization = await flow.start()
    return flow, session, clock, authorization


async def _expect_error(call, code: IntegrationSetupErrorCode):
    with pytest.raises(IntegrationSetupError) as error:
        await call
    assert error.value.code == code


class TestStart:
    @pytest.mark.asyncio
    async def test_requests_device_code_and_hides_it(self):
        flow, session, _ = _flow(_response(200, DEVICE_RESPONSE))

        before = datetime.now(tzlocal())
        authorization = await flow.start()

        assert authorization.user_code == "ABCD-1234"
        assert authorization.verification_uri == VERIFICATION_URI
        assert authorization.interval == 5
        assert authorization.flow_id and authorization.flow_id != DEVICE_CODE
        assert DEVICE_CODE not in repr(authorization)
        assert authorization.expires_at.tzinfo is not None
        assert authorization.expires_at - before >= timedelta(seconds=899)

        call = session.post.await_args
        assert call.args[0] == DEVICE_CODE_URL
        assert call.kwargs["data"] == {"client_id": CLIENT_ID, "scope": SCOPE}
        assert call.kwargs["headers"] == {"Accept": "application/json"}
        assert call.kwargs["follow_redirects"] is False

    @pytest.mark.asyncio
    async def test_rejects_unexpected_verification_uri(self):
        flow, _, _ = _flow(
            _response(
                200, {**DEVICE_RESPONSE, "verification_uri": "https://evil.test/login"}
            )
        )
        await _expect_error(flow.start(), IntegrationSetupErrorCode.UNKNOWN)

    @pytest.mark.parametrize(
        "body",
        [
            {**DEVICE_RESPONSE, "device_code": ""},
            {**DEVICE_RESPONSE, "user_code": None},
            {**DEVICE_RESPONSE, "expires_in": 0},
            {**DEVICE_RESPONSE, "interval": "5"},
            {"error": "unauthorized_client"},
        ],
    )
    @pytest.mark.asyncio
    async def test_rejects_malformed_responses(self, body):
        flow, _, _ = _flow(_response(200, body))
        await _expect_error(flow.start(), IntegrationSetupErrorCode.UNKNOWN)

    @pytest.mark.asyncio
    async def test_client_errors_without_error_field_are_unknown(self):
        flow, _, _ = _flow(_response(404, {"message": "Not Found"}))
        await _expect_error(flow.start(), IntegrationSetupErrorCode.UNKNOWN)

    @pytest.mark.parametrize(
        "response",
        [
            _response(502, {"message": "bad gateway"}),
            _response(429, {"message": "slow"}),
            _response(200, "<html>"),
            httpx.ConnectError("offline"),
        ],
    )
    @pytest.mark.asyncio
    async def test_transient_failures_are_unreachable(self, response):
        flow, _, _ = _flow(response)
        await _expect_error(flow.start(), IntegrationSetupErrorCode.UNREACHABLE)

    @pytest.mark.asyncio
    async def test_new_start_replaces_previous_flow(self):
        flow, _, clock = _flow(
            _response(200, DEVICE_RESPONSE),
            _response(200, {**DEVICE_RESPONSE, "user_code": "WXYZ-9876"}),
        )
        first = await flow.start()
        second = await flow.start()
        clock.advance(10)

        await _expect_error(
            flow.poll(first.flow_id), IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED
        )
        assert second.flow_id != first.flow_id


class TestPoll:
    @pytest.mark.asyncio
    async def test_early_poll_does_not_call_github(self):
        flow, session, _, authorization = await _started()

        result = await flow.poll(authorization.flow_id)

        assert result.status == DeviceAuthorizationStatus.PENDING
        assert result.interval == 5
        assert session.post.await_count == 1

    @pytest.mark.asyncio
    async def test_pending_then_authorized(self):
        flow, session, clock, authorization = await _started(
            _response(200, {"error": "authorization_pending"}),
            _response(
                200,
                {"access_token": "gho_token", "token_type": "bearer", "scope": SCOPE},
            ),
        )

        clock.advance(5)
        pending = await flow.poll(authorization.flow_id)
        assert pending.status == DeviceAuthorizationStatus.PENDING

        clock.advance(4)
        await flow.poll(authorization.flow_id)
        assert session.post.await_count == 2

        clock.advance(1)
        result = await flow.poll(authorization.flow_id)

        assert result.status == DeviceAuthorizationStatus.AUTHORIZED
        assert result.payload == {
            "access_token": "gho_token",
            "token_type": "bearer",
            "scope": SCOPE,
        }
        call = session.post.await_args
        assert call.args[0] == ACCESS_TOKEN_URL
        assert call.kwargs["data"] == {
            "client_id": CLIENT_ID,
            "device_code": DEVICE_CODE,
            "grant_type": DEVICE_GRANT_TYPE,
        }
        await _expect_error(
            flow.poll(authorization.flow_id),
            IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED,
        )

    @pytest.mark.asyncio
    async def test_slow_down_increases_interval(self):
        flow, _, clock, authorization = await _started(
            _response(200, {"error": "slow_down", "interval": 7}),
            _response(200, {"error": "slow_down", "interval": 20}),
        )

        clock.advance(5)
        first = await flow.poll(authorization.flow_id)
        assert first.interval == 10

        clock.advance(10)
        second = await flow.poll(authorization.flow_id)
        assert second.interval == 20

    @pytest.mark.parametrize(
        "error, code",
        [
            ("access_denied", IntegrationSetupErrorCode.AUTHORIZATION_DENIED),
            ("expired_token", IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED),
            ("incorrect_client_credentials", IntegrationSetupErrorCode.UNKNOWN),
        ],
    )
    @pytest.mark.asyncio
    async def test_terminal_errors_end_the_flow(self, error, code):
        flow, _, clock, authorization = await _started(_response(200, {"error": error}))

        clock.advance(5)
        await _expect_error(flow.poll(authorization.flow_id), code)
        await _expect_error(
            flow.poll(authorization.flow_id),
            IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED,
        )

    @pytest.mark.asyncio
    async def test_transient_errors_keep_waiting(self):
        flow, _, clock, authorization = await _started(
            httpx.ReadTimeout("timeout"),
            _response(503, {"message": "unavailable"}),
        )

        clock.advance(5)
        assert (
            await flow.poll(authorization.flow_id)
        ).status == DeviceAuthorizationStatus.PENDING
        clock.advance(5)
        assert (
            await flow.poll(authorization.flow_id)
        ).status == DeviceAuthorizationStatus.PENDING

    @pytest.mark.asyncio
    async def test_unknown_flow_is_expired(self):
        flow, _, _, _ = await _started()
        await _expect_error(
            flow.poll("forged"), IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED
        )

    @pytest.mark.asyncio
    async def test_expired_flow_does_not_call_github(self):
        flow, session, clock, authorization = await _started()

        clock.advance(900)

        await _expect_error(
            flow.poll(authorization.flow_id),
            IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED,
        )
        assert session.post.await_count == 1
