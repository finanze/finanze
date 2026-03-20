from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from infrastructure.client.keychain.public_keychain_client import PublicKeychainClient


def _make_client_with_mock_session(response_json: dict, ok: bool = True):
    client = PublicKeychainClient()
    mock_response = MagicMock()
    mock_response.ok = ok
    mock_response.json = AsyncMock(return_value=response_json)

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    client._session = mock_session
    return client, mock_session


class TestFetchParsesResponse:
    @pytest.mark.asyncio
    async def test_returns_entries_from_json(self):
        response = {
            "version": 1,
            "algo": 1,
            "entries": {
                "abc123": "encoded_val_1",
                "def456": "encoded_val_2",
            },
        }
        client, _ = _make_client_with_mock_session(response)

        result = await client.fetch()

        assert len(result) == 2
        keys = {e.key for e in result}
        assert keys == {"abc123", "def456"}
        for entry in result:
            assert entry.algo == 1
            assert entry.version == 1
            assert isinstance(entry.updated_at, datetime)


class TestFetchEmptyEntries:
    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_entries(self):
        response = {"version": 1, "algo": 1, "entries": {}}
        client, _ = _make_client_with_mock_session(response)

        result = await client.fetch()

        assert result == []


class TestFetchHandlesError:
    @pytest.mark.asyncio
    async def test_returns_empty_list_on_exception(self):
        client = PublicKeychainClient()
        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=Exception("Network error"))
        client._session = mock_session

        result = await client.fetch()

        assert result == []


class TestFetchCallsCorrectUrl:
    @pytest.mark.asyncio
    async def test_uses_correct_url_and_timeout(self):
        response = {"version": 1, "algo": 1, "entries": {}}
        client, mock_session = _make_client_with_mock_session(response)

        await client.fetch()

        mock_session.get.assert_called_once_with(
            "https://features.api.finanze.me/keys", timeout=2
        )
