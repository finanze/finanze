import pytest
from unittest.mock import AsyncMock

from application.use_cases.handle_cloud_auth import HandleCloudAuthImpl
from domain.cloud_auth import (
    CloudAuthRequest,
    CloudAuthToken,
    CloudAuthTokenData,
    CloudUserRole,
)


class TestHandleCloudAuthClearsAuth:
    @pytest.mark.asyncio
    async def test_clears_auth_when_token_is_none(self):
        cloud_register = AsyncMock()
        use_case = HandleCloudAuthImpl(cloud_register=cloud_register)
        request = CloudAuthRequest(token=None)

        result = await use_case.execute(request)

        cloud_register.clear_auth.assert_called_once()
        assert result.role is None
        assert result.permissions == []

    @pytest.mark.asyncio
    async def test_clears_auth_when_access_token_is_empty(self):
        cloud_register = AsyncMock()
        use_case = HandleCloudAuthImpl(cloud_register=cloud_register)
        token = CloudAuthToken(
            access_token="",
            refresh_token="ref",
            token_type="Bearer",
            expires_at=0,
        )
        request = CloudAuthRequest(token=token)

        result = await use_case.execute(request)

        cloud_register.clear_auth.assert_called_once()
        assert result.role is None
        assert result.permissions == []

    @pytest.mark.asyncio
    async def test_clears_auth_when_access_token_is_whitespace(self):
        cloud_register = AsyncMock()
        use_case = HandleCloudAuthImpl(cloud_register=cloud_register)
        token = CloudAuthToken(
            access_token="   ",
            refresh_token="ref",
            token_type="Bearer",
            expires_at=0,
        )
        request = CloudAuthRequest(token=token)

        result = await use_case.execute(request)

        cloud_register.clear_auth.assert_called_once()
        assert result.role is None
        assert result.permissions == []


class TestHandleCloudAuthSavesAuth:
    @pytest.mark.asyncio
    async def test_saves_auth_and_returns_role_permissions_when_valid_token(self):
        token_data = CloudAuthTokenData(
            email="user@example.com",
            role=CloudUserRole.PLUS,
            permissions=["backup.create", "backup.info"],
        )
        cloud_register = AsyncMock()
        cloud_register.decode_token.return_value = token_data
        use_case = HandleCloudAuthImpl(cloud_register=cloud_register)
        token = CloudAuthToken(
            access_token="valid_access_token",
            refresh_token="refresh",
            token_type="Bearer",
            expires_at=9999999999,
        )
        request = CloudAuthRequest(token=token)

        result = await use_case.execute(request)

        cloud_register.decode_token.assert_called_once_with("valid_access_token")
        cloud_register.save_auth.assert_called_once_with(token)
        cloud_register.clear_auth.assert_not_called()
        assert result.role == CloudUserRole.PLUS
        assert result.permissions == ["backup.create", "backup.info"]
