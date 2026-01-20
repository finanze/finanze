import httpx


class HttpResponse:
    def __init__(self, response: httpx.Response):
        self._response = response

    @property
    def ok(self) -> bool:
        return self._response.is_success

    @property
    def status(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._response.headers)

    def raise_for_status(self):
        return self._response.raise_for_status()

    async def json(self):
        return self._response.json()

    async def text(self) -> str:
        return self._response.text

    async def read(self) -> bytes:
        return self._response.content

    async def release(self):
        self._response.close()

    async def aclose(self):
        await self.release()
