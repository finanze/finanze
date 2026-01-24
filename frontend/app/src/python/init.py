from finanze.app import MobileApp
from finanze.logs import configure_logging

app = MobileApp()


async def initialize(operative_system: str | None = None):
    configure_logging()
    await app.initialize(operative_system=operative_system)


async def initialize_deferred():
    await app.initialize_deferred()
