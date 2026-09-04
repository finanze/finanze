import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domain.exception.exceptions import (
    AddressNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    TooManyRequests,
)
from infrastructure.client.crypto.zerion.zerion_client import ZerionClient

FAKE_API_KEY = "fake-zerion-api-key"
FAKE_ADDRESS = "0xFAKE0000000000000000000000000000000001"


def _mock_response(status: int, ok: bool, json_body: dict | None = None):
    response = MagicMock()
    response.status = status
    response.ok = ok
    response.text = AsyncMock(return_value="mock error body")
    if json_body is not None:
        response.json = AsyncMock(return_value=json_body)
    return response


def _patched_session(mock_session):
    return patch(
        "infrastructure.client.crypto.zerion.zerion_client.get_http_session",
        return_value=mock_session,
    )


class TestSetup:
    @pytest.mark.asyncio
    async def test_raises_invalid_credentials_on_401(self):
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=_mock_response(401, ok=False))

        with _patched_session(mock_session):
            client = ZerionClient()
            with pytest.raises(IntegrationSetupError) as exc_info:
                await client.setup({"api_key": FAKE_API_KEY})

        assert exc_info.value.code == IntegrationSetupErrorCode.INVALID_CREDENTIALS

    @pytest.mark.asyncio
    async def test_raises_invalid_credentials_on_403(self):
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=_mock_response(403, ok=False))

        with _patched_session(mock_session):
            client = ZerionClient()
            with pytest.raises(IntegrationSetupError) as exc_info:
                await client.setup({"api_key": FAKE_API_KEY})

        assert exc_info.value.code == IntegrationSetupErrorCode.INVALID_CREDENTIALS

    @pytest.mark.asyncio
    async def test_raises_too_many_requests_on_429(self):
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=_mock_response(429, ok=False))

        with (
            _patched_session(mock_session),
            patch(
                "infrastructure.client.crypto.zerion.zerion_client.asyncio.sleep",
                AsyncMock(),
            ),
        ):
            client = ZerionClient()
            with pytest.raises(TooManyRequests):
                await client.setup({"api_key": FAKE_API_KEY})

    @pytest.mark.asyncio
    async def test_returns_normally_on_200(self):
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=_mock_response(200, ok=True))

        with _patched_session(mock_session):
            client = ZerionClient()
            await client.setup({"api_key": FAKE_API_KEY})

        mock_session.get.assert_awaited_once()
        called_url = mock_session.get.await_args.args[0]
        assert called_url == "https://api.zerion.io/v1/chains/"

        headers = mock_session.get.await_args.kwargs["headers"]
        expected_token = base64.b64encode(f"{FAKE_API_KEY}:".encode()).decode()
        assert headers["Authorization"] == f"Basic {expected_token}"
        assert "Mozilla" in headers["User-Agent"]


class TestFetchPositions:
    @pytest.mark.asyncio
    async def test_sends_auth_ua_and_query_params_and_returns_data(self):
        fake_data = [
            {
                "type": "positions",
                "id": "fake-position-1",
                "attributes": {
                    "value": 123.45,
                    "quantity": {"float": 1.0, "decimals": 18},
                },
            }
        ]
        mock_session = MagicMock()
        mock_session.get = AsyncMock(
            return_value=_mock_response(200, ok=True, json_body={"data": fake_data})
        )

        with _patched_session(mock_session):
            client = ZerionClient()
            result = await client.fetch_positions(
                FAKE_API_KEY, FAKE_ADDRESS, positions_filter="no_filter"
            )

        assert result == fake_data

        mock_session.get.assert_awaited_once()
        called_url = mock_session.get.await_args.args[0]
        assert called_url.startswith(
            f"https://api.zerion.io/v1/wallets/{FAKE_ADDRESS}/positions/"
        )
        assert "filter[positions]=no_filter" in called_url
        assert "filter[trash]=only_non_trash" in called_url
        assert "currency=eur" in called_url

        headers = mock_session.get.await_args.kwargs["headers"]
        expected_token = base64.b64encode(f"{FAKE_API_KEY}:".encode()).decode()
        assert headers["Authorization"] == f"Basic {expected_token}"
        assert "Mozilla" in headers["User-Agent"]

    @pytest.mark.asyncio
    async def test_defaults_positions_filter_to_only_complex(self):
        mock_session = MagicMock()
        mock_session.get = AsyncMock(
            return_value=_mock_response(200, ok=True, json_body={"data": []})
        )

        with _patched_session(mock_session):
            client = ZerionClient()
            result = await client.fetch_positions(FAKE_API_KEY, FAKE_ADDRESS)

        assert result == []
        called_url = mock_session.get.await_args.args[0]
        assert "filter[positions]=only_complex" in called_url

    @pytest.mark.asyncio
    async def test_raises_too_many_requests_on_429(self):
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=_mock_response(429, ok=False))

        with (
            _patched_session(mock_session),
            patch(
                "infrastructure.client.crypto.zerion.zerion_client.asyncio.sleep",
                AsyncMock(),
            ),
        ):
            client = ZerionClient()
            with pytest.raises(TooManyRequests):
                await client.fetch_positions(FAKE_API_KEY, FAKE_ADDRESS)

    @pytest.mark.asyncio
    async def test_raises_address_not_found_on_400(self):
        # Zerion returns HTTP 200 for any valid address (even an empty one)
        # and HTTP 400 for a malformed/invalid address - it never 404s.
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=_mock_response(400, ok=False))

        with _patched_session(mock_session):
            client = ZerionClient()
            with pytest.raises(AddressNotFound):
                await client.fetch_positions(FAKE_API_KEY, FAKE_ADDRESS)


class TestFetchPositionsResilience:
    @pytest.mark.asyncio
    async def test_retries_503_honouring_retry_after_then_returns(self):
        r503 = _mock_response(503, ok=False)
        r503.headers = {"Retry-After": "2"}
        r200 = _mock_response(200, ok=True, json_body={"data": [{"id": "p1"}]})
        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=[r503, r200])

        with (
            _patched_session(mock_session),
            patch(
                "infrastructure.client.crypto.zerion.zerion_client.asyncio.sleep",
                new=AsyncMock(),
            ) as sleep,
        ):
            client = ZerionClient()
            data = await client.fetch_positions(FAKE_API_KEY, FAKE_ADDRESS)

        assert data == [{"id": "p1"}]
        assert mock_session.get.await_count == 2
        assert sleep.await_args.args[0] == 2

    @pytest.mark.asyncio
    async def test_raises_invalid_credentials_on_401_during_fetch(self):
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=_mock_response(401, ok=False))

        with _patched_session(mock_session):
            client = ZerionClient()
            with pytest.raises(IntegrationSetupError):
                await client.fetch_positions(FAKE_API_KEY, FAKE_ADDRESS)

    @pytest.mark.asyncio
    async def test_address_is_percent_encoded_in_path(self):
        mock_session = MagicMock()
        mock_session.get = AsyncMock(
            return_value=_mock_response(200, ok=True, json_body={"data": []})
        )

        with _patched_session(mock_session):
            client = ZerionClient()
            await client.fetch_positions(FAKE_API_KEY, "0xabc/../x?y#z")

        call = mock_session.get.await_args
        url = call.args[0] if call.args else call.kwargs.get("url")
        assert "0xabc%2F..%2Fx%3Fy%23z" in url
        assert "/../" not in url
