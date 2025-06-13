from application.ports.config_port import ConfigPort
from domain.settings import Settings
from domain.use_cases.update_settings import UpdateSettings


class UpdateSettingsImpl(UpdateSettings):
    def __init__(self, config_port: ConfigPort):
        self._config_port = config_port

    def execute(self, new_config: Settings):
        self._config_port.save(new_config)
