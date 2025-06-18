from domain.settings import FetchConfig, GeneralConfig, Settings, VirtualFetchConfig

CURRENT_VERSION = 2

BASE_CONFIG = Settings(
    version=CURRENT_VERSION,
    general=GeneralConfig(defaultCurrency="EUR"),
    fetch=FetchConfig(updateCooldown=60, virtual=VirtualFetchConfig()),
)
