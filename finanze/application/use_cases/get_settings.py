from typing import Optional

from application.ports.config_port import ConfigPort
from domain.settings import PartialSettings, SettingsSection
from domain.use_cases.get_settings import GetSettings


class GetSettingsImpl(GetSettings):
    def __init__(self, config_port: ConfigPort):
        self._config_port = config_port

    async def execute(
        self, sections: Optional[set[SettingsSection]] = None
    ) -> PartialSettings:
        return await self._config_port.load_sections(sections or set(SettingsSection))
