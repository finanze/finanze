import json

import httpx
import js
from pyodide.ffi import to_js

from infrastructure.client.http.http_response import HttpResponse


class NoCookieTransport(httpx.AsyncHTTPTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request.headers.pop("cookie", None)

        response = await super().handle_async_request(request)

        response.headers.pop("set-cookie", None)

        return response


_httpx_singleton_client: httpx.AsyncClient | None = None


class HttpSession:
    """
    Mobile-specific implementation using AsyncClient directly.
    """

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


class _TlsHttpResponse:
    def __init__(self, status_code: int, headers: dict, data: str):
        self._status_code = status_code
        self._headers = headers
        self._data = data

    @property
    def ok(self) -> bool:
        return 200 <= self._status_code < 400

    @property
    def status(self) -> int:
        return self._status_code

    @property
    def headers(self) -> dict[str, str]:
        return self._headers

    def raise_for_status(self):
        if not self.ok:
            raise httpx.HTTPStatusError(
                message=f"{self._status_code}",
                request=httpx.Request("GET", ""),
                response=httpx.Response(self._status_code),
            )

    async def json(self):
        return json.loads(self._data)

    async def text(self) -> str:
        return self._data

    async def read(self) -> bytes:
        return self._data.encode("utf-8")


class ImpersonatedHttpSession:
    _PROFILE_MAP = {
        "firefox135": "firefox_135",
        "chrome133": "chrome_133",
        "safari_ios_18_0": "safari_ios_18_0",
        "safari_ios_18_5": "safari_ios_18_5",
    }

    def __init__(
        self,
        impersonate: str = "firefox135",
        force_http1: bool = False,
        disable_http3: bool = False,
    ):
        self._session_id = f"tls-{id(self)}"
        self._headers = {}
        self._profile = self._PROFILE_MAP.get(impersonate, impersonate)
        self._force_http1 = force_http1
        self._disable_http3 = disable_http3

    @property
    def headers(self):
        return self._headers

    @property
    def cookies(self):
        return httpx.Cookies()

    @property
    def cookie_jar(self):
        return self.cookies.jar

    async def request(self, method: str, url: str, **kwargs) -> _TlsHttpResponse:
        headers = kwargs.pop("headers", None)
        merged = dict(self._headers)
        if headers:
            merged.update(headers)

        body = None
        if "json" in kwargs and kwargs["json"] is not None:
            body = json.dumps(kwargs.pop("json"))
            if "Content-Type" not in merged and "content-type" not in merged:
                merged["Content-Type"] = "application/json"
        elif "data" in kwargs and kwargs["data"] is not None:
            data = kwargs.pop("data")
            if isinstance(data, dict):
                body = "&".join(f"{k}={v}" for k, v in data.items())
                if "Content-Type" not in merged and "content-type" not in merged:
                    merged["Content-Type"] = "application/x-www-form-urlencoded"
            else:
                body = str(data)

        kwargs.pop("json", None)
        kwargs.pop("data", None)

        params = kwargs.pop("params", None)
        if params:
            from urllib.parse import urlencode

            sep = "&" if "?" in url else "?"
            url = (
                url
                + sep
                + urlencode({k: v for k, v in params.items() if v is not None})
            )

        options = {
            "url": url,
            "method": method,
            "headers": merged,
            "sessionId": self._session_id,
            "profile": self._profile,
        }
        if body:
            options["data"] = body
        if self._force_http1:
            options["forceHttp1"] = True
        if self._disable_http3:
            options["disableHttp3"] = True

        response_js = await js.TlsHttp.request(to_js(options, create_pyproxies=False))
        response_py = response_js.to_py() if hasattr(response_js, "to_py") else {}

        status = int(response_py.get("status", 0))
        resp_headers = response_py.get("headers", {})
        if not isinstance(resp_headers, dict):
            resp_headers = {}
        data_str = response_py.get("data", "")
        if not isinstance(data_str, str):
            data_str = str(data_str) if data_str is not None else ""

        return _TlsHttpResponse(status, resp_headers, data_str)


def new_impersonated_http_session(
    impersonate: str = "firefox135",
    force_http1: bool = False,
    disable_http3: bool = False,
) -> ImpersonatedHttpSession:
    return ImpersonatedHttpSession(
        impersonate=impersonate, force_http1=force_http1, disable_http3=disable_http3
    )
