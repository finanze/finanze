import pytest
from unittest.mock import AsyncMock

from application.use_cases.update_settings import UpdateSettingsImpl
from domain.settings import GeneralConfig, LabelingConfig, PartialSettings


class TestUpdateSettingsExecute:
    @pytest.mark.asyncio
    async def test_execute_calls_save_with_given_settings(self):
        config_port = AsyncMock()
        use_case = UpdateSettingsImpl(config_port=config_port)
        settings = PartialSettings(general=GeneralConfig(defaultCurrency="USD"))

        await use_case.execute(settings)

        config_port.save.assert_called_once_with(settings)

    @pytest.mark.asyncio
    async def test_execute_passes_only_given_sections(self):
        config_port = AsyncMock()
        use_case = UpdateSettingsImpl(config_port=config_port)
        settings = PartialSettings(labeling=LabelingConfig())

        await use_case.execute(settings)

        saved = config_port.save.call_args[0][0]
        assert saved.labeling == LabelingConfig()
        assert saved.general is None
        assert saved.assets is None

    @pytest.mark.asyncio
    async def test_execute_can_be_called_multiple_times(self):
        config_port = AsyncMock()
        use_case = UpdateSettingsImpl(config_port=config_port)

        await use_case.execute(PartialSettings(general=GeneralConfig()))
        await use_case.execute(PartialSettings(labeling=LabelingConfig()))

        assert config_port.save.call_count == 2
