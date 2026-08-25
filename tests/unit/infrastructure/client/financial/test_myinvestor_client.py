from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.entity_login import (
    ChallengeType,
    LoginConfirmationType,
    LoginOptions,
    LoginResultCode,
)
from infrastructure.client.entity.financial.myinvestor.v2.myinvestor_client import (
    MyInvestorAPIV2Client,
)

SIGNATURE_REQUEST_ID = "2625a7cd-0c61-456c-b1c1-4cf562cc280e"
SIGNATURE_ID = "V98mXi53AL"
OTP_ID = "VBOTHBLW"


class FakeResponse:
    def __init__(self, *, status=200, json_data=None):
        self.status = status
        self.ok = 200 <= status < 400
        self._json = json_data if json_data is not None else {}

    async def json(self):
        return self._json

    async def text(self):
        return ""


def _token_payload():
    return {
        "payload": {
            "data": {
                "accessToken": "access",
                "refreshToken": "refresh",
                "refreshExpiresIn": 1800,
            }
        }
    }


def _pending_sms_payload(signature_request_id=SIGNATURE_REQUEST_ID):
    return {
        "payload": {
            "data": {
                "signatureRequestId": signature_request_id,
                "status": "PENDING",
                "pendingSignatureMethods": [["OTP_SMS", "OTP_PUSH"]],
            }
        },
        "status": {"code": "ACCEPTED"},
    }


def _sms_sent_payload():
    return {
        "payload": {
            "data": {
                "type": "OTP",
                "signatureId": SIGNATURE_ID,
                "method": "OTP_SMS",
                "channel": "SMS",
                "destination": "******447",
            }
        }
    }


def _sms_complete_payload():
    return {
        "payload": {
            "data": {
                "signatureRequestId": SIGNATURE_REQUEST_ID,
                "operative": "LOGIN",
                "status": "COMPLETE",
                "pendingSignatureMethods": [],
            }
        }
    }


def _legacy_otp_payload():
    return {
        "payload": {
            "data": {
                "otpId": OTP_ID,
                "signatureRequestId": SIGNATURE_REQUEST_ID,
                "otpMedia": "SMS",
                "code": "PENDING_OTP",
            }
        }
    }


def _captcha_required():
    return FakeResponse(
        status=403,
        json_data={"status": {"code": "SECURITY_001", "message": "Captcha required"}},
    )


def _make_client(side_effect):
    client = MyInvestorAPIV2Client()
    client._post_request = AsyncMock(side_effect=side_effect)
    return client


async def _login(client, **kwargs):
    return await client.login(
        "71739020L",
        "secret",
        login_options=kwargs.pop("login_options", LoginOptions()),
        session=kwargs.pop("session", None),
        process_id=kwargs.pop("process_id", None),
        code=kwargs.pop("code", None),
        captcha_token=kwargs.pop("captcha_token", None),
        keychain=kwargs.pop("keychain", None),
    )


class TestMyInvestorLoginCaptcha:
    @pytest.mark.asyncio
    async def test_returns_recaptcha_challenge_on_security_001(self):
        client = _make_client([_captcha_required()])
        keychain = MagicMock()
        keychain.get.return_value.decode.return_value = "site-key"

        result = await _login(client, keychain=keychain)

        assert result.code == LoginResultCode.CODE_REQUESTED
        assert result.confirmation_type == LoginConfirmationType.CHALLENGE
        assert result.challenge_type == ChallengeType.RECAPTCHA
        assert result.process_id == "site-key"
        assert result.details["challenge_domain"] == "myinvestor.es"


class TestMyInvestorLoginSmsOtp:
    @pytest.mark.asyncio
    async def test_202_requests_sms_and_returns_process_id(self):
        client = _make_client(
            [
                FakeResponse(status=202, json_data=_pending_sms_payload()),
                FakeResponse(status=200, json_data=_sms_sent_payload()),
            ]
        )

        result = await _login(client, captcha_token="captcha")

        assert result.code == LoginResultCode.CODE_REQUESTED
        assert result.process_id == f"{SIGNATURE_REQUEST_ID}|{SIGNATURE_ID}"
        assert result.confirmation_type is None
        assert client._post_request.call_count == 2
        token_call, sms_call = client._post_request.call_args_list
        assert token_call.args[0] == "/login/api/v2/auth/token"
        assert token_call.kwargs["body"] == {
            "customerId": "71739020L",
            "password": "secret",
        }
        assert token_call.kwargs["headers"]["X-Recaptcha-Token"] == "captcha"
        assert token_call.kwargs["headers"]["X-Recaptcha-Action"] == "SECURITY_CHECK"
        assert (
            sms_call.args[0]
            == f"/signature/api/v3/public/signature/{SIGNATURE_REQUEST_ID}?method=OTP_SMS"
        )
        assert sms_call.kwargs["body"] is None

    @pytest.mark.asyncio
    async def test_avoid_new_login_skips_sms(self):
        client = _make_client(
            [FakeResponse(status=202, json_data=_pending_sms_payload())]
        )

        result = await _login(client, login_options=LoginOptions(avoid_new_login=True))

        assert result.code == LoginResultCode.NOT_LOGGED
        assert client._post_request.call_count == 1

    @pytest.mark.asyncio
    async def test_legacy_otp_id_still_supported(self):
        client = _make_client(
            [FakeResponse(status=202, json_data=_legacy_otp_payload())]
        )

        result = await _login(client)

        assert result.code == LoginResultCode.CODE_REQUESTED
        assert result.process_id == f"{OTP_ID}|{SIGNATURE_REQUEST_ID}"
        assert client._post_request.call_count == 1


class TestMyInvestorCompleteSmsOtp:
    @pytest.mark.asyncio
    async def test_validates_sms_then_requests_token(self):
        client = _make_client(
            [
                FakeResponse(status=200, json_data=_sms_complete_payload()),
                FakeResponse(status=200, json_data=_token_payload()),
            ]
        )
        client._device_id = "device-1"

        result = await _login(
            client,
            process_id=f"{SIGNATURE_REQUEST_ID}|{SIGNATURE_ID}",
            code="951677",
        )

        assert result.code == LoginResultCode.CREATED
        assert result.session.payload["device_id"] == "device-1"
        assert client._signature_complete is False
        validate_call, token_call = client._post_request.call_args_list
        assert (
            validate_call.args[0]
            == f"/signature/api/v3/public/signature/{SIGNATURE_REQUEST_ID}/validate/{SIGNATURE_ID}"
        )
        assert validate_call.kwargs["body"] == {"code": "951677"}
        assert token_call.args[0] == "/login/api/v2/auth/token"
        assert token_call.kwargs["body"] == {
            "customerId": "71739020L",
            "password": "secret",
        }

    @pytest.mark.asyncio
    async def test_invalid_sms_code(self):
        client = _make_client([FakeResponse(status=400)])

        result = await _login(
            client,
            process_id=f"{SIGNATURE_REQUEST_ID}|{SIGNATURE_ID}",
            code="000000",
        )

        assert result.code == LoginResultCode.INVALID_CODE
        assert client._signature_complete is False
        assert client._post_request.call_count == 1

    @pytest.mark.asyncio
    async def test_short_code_rejected_without_request(self):
        client = _make_client([])

        result = await _login(
            client,
            process_id=f"{SIGNATURE_REQUEST_ID}|{SIGNATURE_ID}",
            code="123",
        )

        assert result.code == LoginResultCode.INVALID_CODE
        client._post_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_token_after_otp_can_request_captcha(self):
        client = _make_client(
            [
                FakeResponse(status=200, json_data=_sms_complete_payload()),
                _captcha_required(),
            ]
        )

        result = await _login(
            client,
            process_id=f"{SIGNATURE_REQUEST_ID}|{SIGNATURE_ID}",
            code="951677",
        )

        assert result.code == LoginResultCode.CODE_REQUESTED
        assert result.confirmation_type == LoginConfirmationType.CHALLENGE
        assert client._signature_complete is True

    @pytest.mark.asyncio
    async def test_post_otp_captcha_retry_requests_token_only(self):
        client = _make_client([FakeResponse(status=200, json_data=_token_payload())])
        client._signature_complete = True
        client._device_id = "device-1"

        result = await _login(client, captcha_token="fresh-captcha")

        assert result.code == LoginResultCode.CREATED
        assert result.session.payload["device_id"] == "device-1"
        assert client._signature_complete is False
        assert client._post_request.call_count == 1
        token_call = client._post_request.call_args
        assert token_call.args[0] == "/login/api/v2/auth/token"
        assert token_call.kwargs["headers"]["X-Recaptcha-Token"] == "fresh-captcha"

    @pytest.mark.asyncio
    async def test_legacy_otp_complete_sends_code_on_token(self):
        client = _make_client([FakeResponse(status=200, json_data=_token_payload())])

        result = await _login(
            client,
            process_id=f"{OTP_ID}|{SIGNATURE_REQUEST_ID}",
            code="123456",
        )

        assert result.code == LoginResultCode.CREATED
        token_call = client._post_request.call_args
        assert token_call.kwargs["body"] == {
            "customerId": "71739020L",
            "password": "secret",
            "otpId": OTP_ID,
            "signatureRequestId": SIGNATURE_REQUEST_ID,
            "code": "123456",
        }


class TestMyInvestorLoginDeviceId:
    @pytest.mark.asyncio
    async def test_reuses_device_id_across_captcha_retry(self):
        client = _make_client(
            [
                _captcha_required(),
                FakeResponse(status=202, json_data=_pending_sms_payload()),
                FakeResponse(status=200, json_data=_sms_sent_payload()),
            ]
        )

        first = await _login(client)
        device_id = client._device_id
        assert first.code == LoginResultCode.CODE_REQUESTED
        assert device_id

        second = await _login(client, captcha_token="captcha")
        assert second.code == LoginResultCode.CODE_REQUESTED
        assert client._device_id == device_id
        token_headers = client._post_request.call_args_list[1].kwargs["headers"]
        assert token_headers["x-device-id"] == device_id
