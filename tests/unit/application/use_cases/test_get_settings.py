import pytest
from unittest.mock import AsyncMock

from application.use_cases.get_settings import GetSettingsImpl
from domain.settings import PartialSettings, SettingsSection


class TestGetSettingsExecute:
    @pytest.mark.asyncio
    async def test_loads_all_sections_by_default(self):
        config_port = AsyncMock()
        config_port.load_sections.return_value = PartialSettings()
        use_case = GetSettingsImpl(config_port)

        await use_case.execute()

        config_port.load_sections.assert_awaited_once_with(set(SettingsSection))

    @pytest.mark.asyncio
    async def test_empty_selection_loads_all_sections(self):
        config_port = AsyncMock()
        use_case = GetSettingsImpl(config_port)

        await use_case.execute(set())

        config_port.load_sections.assert_awaited_once_with(set(SettingsSection))

    @pytest.mark.asyncio
    async def test_loads_only_requested_sections(self):
        config_port = AsyncMock()
        expected = PartialSettings(lastUpdate="x")
        config_port.load_sections.return_value = expected
        use_case = GetSettingsImpl(config_port)

        result = await use_case.execute({SettingsSection.LABELING})

        config_port.load_sections.assert_awaited_once_with({SettingsSection.LABELING})
        assert result is expected
