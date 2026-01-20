from init import app


async def handle(method, path, body, headers):
    return await app.router.handle(method, path, body, headers)
