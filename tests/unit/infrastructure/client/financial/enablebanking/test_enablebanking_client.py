from unittest.mock import AsyncMock, MagicMock

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from domain.exception.exceptions import (
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    TooManyRequests,
)
from infrastructure.client.financial.enablebanking.enablebanking_client import (
    EnableBankingClient,
)


@pytest.fixture
def rsa_private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


class FakeResponse:
    def __init__(self, *, ok=True, status=200, json_data=None, text_data=""):
        self.ok = ok
        self.status = status
        self._json = json_data if json_data is not None else {}
        self._text = text_data

    async def json(self):
        return self._json

    async def text(self):
        return self._text

    def raise_for_status(self):
        if not self.ok:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "https://api.enablebanking.com"),
                response=httpx.Response(self.status),
            )


def _make_client(response: FakeResponse, pem: str) -> EnableBankingClient:
    client = EnableBankingClient()
    client._application_id = "app-123"
    client._private_key = pem
    client._session = MagicMock()
    client._session.request = AsyncMock(return_value=response)
    return client


class TestBuildJwt:
    def test_jwt_header_and_claims(self, rsa_private_key_pem):
        client = EnableBankingClient()
        client._application_id = "app-123"
        client._private_key = rsa_private_key_pem

        token = client._build_jwt()

        header = jwt.get_unverified_header(token)
        assert header["kid"] == "app-123"
        assert header["alg"] == "RS256"

        public_key = serialization.load_pem_private_key(
            rsa_private_key_pem.encode(), password=None
        ).public_key()
        decoded = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience="api.enablebanking.com",
        )
        assert decoded["iss"] == "enablebanking.com"
        assert decoded["aud"] == "api.enablebanking.com"
        assert decoded["exp"] > decoded["iat"]


class TestSetup:
    @pytest.mark.asyncio
    async def test_setup_success(self, rsa_private_key_pem):
        client = _make_client(
            FakeResponse(json_data={"name": "My App"}), rsa_private_key_pem
        )
        client._application_id = None
        client._private_key = None

        await client.setup(
            {"application_id": "app-123", "private_key": rsa_private_key_pem}
        )

        assert client._application_id == "app-123"
        assert client._private_key == rsa_private_key_pem

    @pytest.mark.asyncio
    async def test_setup_missing_credentials(self, rsa_private_key_pem):
        client = EnableBankingClient()
        with pytest.raises(IntegrationSetupError) as exc:
            await client.setup({"application_id": "app-123"})
        assert exc.value.code == IntegrationSetupErrorCode.INVALID_CREDENTIALS

    @pytest.mark.asyncio
    async def test_setup_invalid_credentials(self, rsa_private_key_pem):
        client = _make_client(
            FakeResponse(ok=False, status=401, text_data="unauthorized"),
            rsa_private_key_pem,
        )
        client._application_id = None
        client._private_key = None

        with pytest.raises(IntegrationSetupError) as exc:
            await client.setup(
                {"application_id": "app-123", "private_key": rsa_private_key_pem}
            )
        assert exc.value.code == IntegrationSetupErrorCode.INVALID_CREDENTIALS


class TestRequests:
    @pytest.mark.asyncio
    async def test_get_aspsps_uses_cache(self, rsa_private_key_pem):
        aspsps = [{"name": "Bank", "country": "ES"}]
        client = _make_client(
            FakeResponse(json_data={"aspsps": aspsps}), rsa_private_key_pem
        )

        first = await client.get_aspsps("ES")
        second = await client.get_aspsps("ES")

        assert first == second == aspsps
        assert client._session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_start_auth_body(self, rsa_private_key_pem):
        client = _make_client(
            FakeResponse(json_data={"url": "https://x", "authorization_id": "auth-1"}),
            rsa_private_key_pem,
        )

        result = await client.start_auth(
            "Bank", "ES", "state-1", "2024-01-01T00:00:00+00:00"
        )

        assert result == {"url": "https://x", "authorization_id": "auth-1"}
        call = client._session.request.call_args
        assert call.args[0] == "POST"
        assert call.args[1].endswith("/auth")
        body = call.kwargs["json"]
        assert body["redirect_url"] == EnableBankingClient.REDIRECT_URL
        assert body["aspsp"] == {"name": "Bank", "country": "ES"}
        assert body["state"] == "state-1"
        assert body["access"] == {"valid_until": "2024-01-01T00:00:00+00:00"}

    @pytest.mark.asyncio
    async def test_create_session(self, rsa_private_key_pem):
        client = _make_client(
            FakeResponse(json_data={"session_id": "sess-1", "accounts": []}),
            rsa_private_key_pem,
        )

        result = await client.create_session("code-1")

        assert result["session_id"] == "sess-1"
        call = client._session.request.call_args
        assert call.args[0] == "POST"
        assert call.args[1].endswith("/sessions")
        assert call.kwargs["json"] == {"code": "code-1"}

    @pytest.mark.asyncio
    async def test_too_many_requests(self, rsa_private_key_pem):
        client = _make_client(
            FakeResponse(ok=False, status=429, text_data="rate limit"),
            rsa_private_key_pem,
        )

        with pytest.raises(TooManyRequests):
            await client.get_account_balances("acc-1")
