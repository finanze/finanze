from domain.settings import Settings, ScrapeConfig, VirtualScrapeConfig

BASE_CONFIG = Settings(
    scrape=ScrapeConfig(updateCooldown=60, virtual=VirtualScrapeConfig())
)
