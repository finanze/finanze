from domain.settings import GeneralConfig, ScrapeConfig, Settings, VirtualScrapeConfig

BASE_CONFIG = Settings(
    general=GeneralConfig(defaultCurrency="EUR"),
    scrape=ScrapeConfig(updateCooldown=60, virtual=VirtualScrapeConfig()),
)
