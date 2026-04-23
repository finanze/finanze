import pytest
from unittest.mock import AsyncMock

from application.use_cases.update_settings import UpdateSettingsImpl
from domain.settings import Settings


class TestUpdateSettingsExecute:
    @pytest.mark.asyncio
    async def test_execute_calls_save_with_given_settings(self):
        config_port = AsyncMock()
        use_case = UpdateSettingsImpl(config_port=config_port)
        settings = Settings(lastUpdate="2025-01-01")

        await use_case.execute(settings)

        config_port.save.assert_called_once_with(settings)

    @pytest.mark.asyncio
    async def test_execute_passes_settings_exactly(self):
        config_port = AsyncMock()
        use_case = UpdateSettingsImpl(config_port=config_port)
        settings = Settings(lastUpdate="2025-06-15", version=5)

        await use_case.execute(settings)

        saved = config_port.save.call_args[0][0]
        assert saved.lastUpdate == "2025-06-15"
        assert saved.version == 5

    @pytest.mark.asyncio
    async def test_execute_can_be_called_multiple_times(self):
        config_port = AsyncMock()
        use_case = UpdateSettingsImpl(config_port=config_port)
        settings_a = Settings(lastUpdate="2025-01-01")
        settings_b = Settings(lastUpdate="2025-02-01")

        await use_case.execute(settings_a)
        await use_case.execute(settings_b)

        assert config_port.save.call_count == 2
