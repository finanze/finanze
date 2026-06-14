from finanze.app_background import MobileBackgroundApp

app = MobileBackgroundApp()


async def initialize(operative_system: str | None = None):
    await app.initialize(operative_system=operative_system)


async def connect(username: str | None = None):
    await app.connect(username)


async def disconnect():
    await app.disconnect()


def is_connected() -> bool:
    return app.connected


async def update_quotes() -> dict:
    return await app.update_quotes()


async def update_loans() -> dict:
    return await app.update_loans()


async def get_networth_timeline(
    base_currency: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    no_calculation: bool = False,
) -> dict:
    return await app.get_networth_timeline(
        base_currency=base_currency,
        from_date=from_date,
        to_date=to_date,
        no_calculation=no_calculation,
    )
