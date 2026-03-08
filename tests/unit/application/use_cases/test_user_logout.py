import pytest
from unittest.mock import AsyncMock, MagicMock

from application.use_cases.user_logout import UserLogoutImpl


class TestUserLogoutExecute:
    def _build_use_case(self):
        config_port = AsyncMock()
        sheets_initiator = MagicMock()
        cloud_register = AsyncMock()
        source_initiator = AsyncMock()
        use_case = UserLogoutImpl(
            source_initiator=source_initiator,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )
        return use_case, config_port, sheets_initiator, cloud_register, source_initiator

    @pytest.mark.asyncio
    async def test_execute_disconnects_config_port(self):
        use_case, config_port, _, _, _ = self._build_use_case()

        await use_case.execute()

        config_port.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_disconnects_sheets_initiator(self):
        use_case, _, sheets_initiator, _, _ = self._build_use_case()

        await use_case.execute()

        sheets_initiator.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_disconnects_cloud_register(self):
        use_case, _, _, cloud_register, _ = self._build_use_case()

        await use_case.execute()

        cloud_register.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_locks_source_initiator(self):
        use_case, _, _, _, source_initiator = self._build_use_case()

        await use_case.execute()

        source_initiator.lock.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_calls_all_four_operations(self):
        use_case, config_port, sheets_initiator, cloud_register, source_initiator = (
            self._build_use_case()
        )

        await use_case.execute()

        config_port.disconnect.assert_called_once()
        sheets_initiator.disconnect.assert_called_once()
        cloud_register.disconnect.assert_called_once()
        source_initiator.lock.assert_called_once()
