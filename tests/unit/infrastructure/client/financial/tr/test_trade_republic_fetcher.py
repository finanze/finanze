from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.entity_login import (
    EntityLoginParams,
    EntityLoginResult,
    LoginResultCode,
    TwoFactor,
)
from domain.public_keychain import PublicKeychain
from infrastructure.client.entity.financial.tr.trade_republic_fetcher import (
    TradeRepublicFetcher,
)


def _make_fetcher():
    fetcher = TradeRepublicFetcher()
    fetcher._client = MagicMock()
    return fetcher


def _make_keychain():
    return MagicMock(spec=PublicKeychain)


class TestFetcherLogin:
    @pytest.mark.asyncio
    async def test_login_delegates_to_client(self):
        fetcher = _make_fetcher()
        expected = EntityLoginResult(LoginResultCode.MANUAL_LOGIN)
        fetcher._client.login = AsyncMock(return_value=expected)

        params = EntityLoginParams(
            credentials={"phone": "+49123", "password": "1234"},
            keychain=_make_keychain(),
        )
        result = await fetcher.login(params)

        assert result.code == LoginResultCode.MANUAL_LOGIN
        fetcher._client.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_with_process_id_and_no_code_calls_complete_login(self):
        fetcher = _make_fetcher()
        expected = EntityLoginResult(LoginResultCode.CREATED)
        fetcher._client.complete_login = AsyncMock(return_value=expected)

        params = EntityLoginParams(
            credentials={"phone": "+49123", "password": "1234", "awsWafToken": "waf"},
            keychain=_make_keychain(),
            two_factor=TwoFactor(process_id="proc-123"),
        )
        result = await fetcher.login(params)

        assert result.code == LoginResultCode.CREATED
        fetcher._client.complete_login.assert_called_once_with("proc-123", "waf")
        fetcher._client.login.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_with_process_id_and_code_delegates_to_login(self):
        fetcher = _make_fetcher()
        expected = EntityLoginResult(LoginResultCode.CREATED)
        fetcher._client.login = AsyncMock(return_value=expected)

        params = EntityLoginParams(
            credentials={"phone": "+49123", "password": "1234", "awsWafToken": "waf"},
            keychain=_make_keychain(),
            two_factor=TwoFactor(process_id="proc-123", code="654321"),
        )
        result = await fetcher.login(params)

        assert result.code == LoginResultCode.CREATED
        fetcher._client.login.assert_called_once()


class TestFetcherCancelLogin:
    def test_cancel_login_delegates_to_client(self):
        fetcher = _make_fetcher()
        fetcher._client.cancel_login = MagicMock()

        fetcher.cancel_login()

        fetcher._client.cancel_login.assert_called_once()
