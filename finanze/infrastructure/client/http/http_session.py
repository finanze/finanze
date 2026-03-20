import httpx

from infrastructure.client.http.http_response import HttpResponse


class NoCookieTransport(httpx.AsyncHTTPTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request.headers.pop("cookie", None)
        response = await super().handle_async_request(request)
        response.headers.pop("set-cookie", None)
        return response


_httpx_singleton_client: httpx.Client | None = None


class HttpSession:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._headers = httpx.Headers(client.headers)

    @property
    def headers(self):
        return self._headers

    @property
    def cookies(self) -> httpx.Cookies:
        return self._client.cookies

    @property
    def cookie_jar(self):
        return self._client.cookies.jar

    def clear_cookies(self) -> None:
        self._client.cookies.jar.clear()

    def set_cookie(self, cookie) -> None:
        self._client.cookies.jar.set_cookie(cookie)

    async def request(self, method: str, url: str, **kwargs) -> HttpResponse:
        headers = kwargs.pop("headers", None)
        if headers is None:
            merged_headers = httpx.Headers(self._headers)
        else:
            merged_headers = httpx.Headers(self._headers)
            merged_headers.update(headers)
        resp = await self._client.request(
            method,
            url,
            headers=dict(merged_headers),
            **kwargs,
        )
        return HttpResponse(resp)

    async def get(self, url: str, **kwargs) -> HttpResponse:
        resp = await self.request("GET", url, **kwargs)
        return resp

    async def post(self, url: str, **kwargs) -> HttpResponse:
        resp = await self.request("POST", url, **kwargs)
        return resp


def get_http_session() -> HttpSession:
    global _httpx_singleton_client
    if _httpx_singleton_client is None:
        _httpx_singleton_client = httpx.AsyncClient(transport=NoCookieTransport())
    return HttpSession(_httpx_singleton_client)


def new_http_session(**kwargs) -> HttpSession:
    return HttpSession(httpx.AsyncClient(**kwargs))


class _CurlCffiResponse:
    def __init__(self, response):
        self._response = response

    @property
    def ok(self) -> bool:
        return 200 <= self._response.status_code < 400

    @property
    def status(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._response.headers)

    def raise_for_status(self):
        from curl_cffi.requests.exceptions import HTTPError

        try:
            self._response.raise_for_status()
        except HTTPError:
            raise httpx.HTTPStatusError(
                message=f"{self._response.status_code}",
                request=httpx.Request("GET", str(self._response.url)),
                response=httpx.Response(self._response.status_code),
            )

    async def json(self):
        return self._response.json()

    async def text(self) -> str:
        return self._response.text

    async def read(self) -> bytes:
        return self._response.content


class ImpersonatedHttpSession:
    def __init__(self, impersonate: str = "firefox135"):
        from curl_cffi.requests import AsyncSession

        self._session = AsyncSession(impersonate=impersonate)
        self._headers = {}

    @property
    def headers(self):
        return self._headers

    @property
    def cookies(self):
        return self._session.cookies

    @property
    def cookie_jar(self):
        return self._session.cookies.jar

    async def request(self, method: str, url: str, **kwargs) -> _CurlCffiResponse:
        headers = kwargs.pop("headers", None)
        merged = dict(self._headers)
        if headers:
            merged.update(headers)
        resp = await self._session.request(method, url, headers=merged, **kwargs)
        return _CurlCffiResponse(resp)


def new_impersonated_http_session(
    impersonate: str = "firefox135",
) -> ImpersonatedHttpSession:
    return ImpersonatedHttpSession(impersonate=impersonate)
