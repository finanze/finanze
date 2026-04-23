import pytest
from unittest.mock import AsyncMock

from application.use_cases.get_cloud_auth import GetCloudAuthImpl
from domain.cloud_auth import CloudAuthData, CloudAuthToken, CloudUserRole


class TestGetCloudAuthReturnsNone:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_auth_data(self):
        cloud_register = AsyncMock()
        cloud_register.get_auth.return_value = None
        use_case = GetCloudAuthImpl(cloud_register=cloud_register)

        result = await use_case.execute()

        assert result is None
        cloud_register.get_auth.assert_called_once()


class TestGetCloudAuthReturnsData:
    @pytest.mark.asyncio
    async def test_returns_auth_data_when_present(self):
        token = CloudAuthToken(
            access_token="access123",
            refresh_token="refresh456",
            token_type="Bearer",
            expires_at=9999999999,
        )
        auth_data = CloudAuthData(
            role=CloudUserRole.PLUS,
            permissions=["backup.create", "backup.info"],
            token=token,
            email="user@example.com",
        )
        cloud_register = AsyncMock()
        cloud_register.get_auth.return_value = auth_data
        use_case = GetCloudAuthImpl(cloud_register=cloud_register)

        result = await use_case.execute()

        assert result is auth_data
        assert result.role == CloudUserRole.PLUS
        assert result.permissions == ["backup.create", "backup.info"]
        assert result.email == "user@example.com"
        assert result.token.access_token == "access123"

    @pytest.mark.asyncio
    async def test_returns_auth_data_with_none_role(self):
        token = CloudAuthToken(
            access_token="tok",
            refresh_token="ref",
            token_type="Bearer",
            expires_at=0,
        )
        auth_data = CloudAuthData(
            role=CloudUserRole.NONE,
            permissions=[],
            token=token,
            email="nobody@example.com",
        )
        cloud_register = AsyncMock()
        cloud_register.get_auth.return_value = auth_data
        use_case = GetCloudAuthImpl(cloud_register=cloud_register)

        result = await use_case.execute()

        assert result is auth_data
        assert result.role == CloudUserRole.NONE
        assert result.permissions == []
