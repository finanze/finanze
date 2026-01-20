import json

import httpx
import js
from pyodide.ffi import to_js


def apply_httpx_patch():
    """
    Patches httpx to handle multipart/form-data requests via Capacitor Native HTTP.
    All other requests go through the original httpx transport.
    """

    if not hasattr(httpx.AsyncHTTPTransport, "_finanze_original_handle_async_request"):
        httpx.AsyncHTTPTransport._finanze_original_handle_async_request = (
            httpx.AsyncHTTPTransport.handle_async_request
        )

    original_handle_async_request = (
        httpx.AsyncHTTPTransport._finanze_original_handle_async_request
    )

    def _split_set_cookie_header(value: str) -> list[str]:
        parts: list[str] = []
        buf: list[str] = []
        in_expires = False
        i = 0
        while i < len(value):
            ch = value[i]
            if not in_expires and value[i : i + 8].lower() == "expires=":
                in_expires = True
                buf.append(value[i : i + 8])
                i += 8
                continue
            if in_expires and ch == ";":
                in_expires = False
                buf.append(ch)
                i += 1
                continue
            if not in_expires and ch == ",":
                candidate = "".join(buf).strip()
                if candidate:
                    parts.append(candidate)
                buf = []
                i += 1
                if i < len(value) and value[i] == " ":
                    i += 1
                continue
            buf.append(ch)
            i += 1

        last = "".join(buf).strip()
        if last:
            parts.append(last)
        return parts

    def _to_httpx_headers(resp_headers: dict) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        for k, v in (resp_headers or {}).items():
            if v is None:
                continue
            key = str(k)
            if isinstance(v, (list, tuple)):
                for one in v:
                    if one is None:
                        continue
                    items.append((key, str(one)))
                continue
            value = str(v)
            if key.lower() == "set-cookie":
                for cookie in _split_set_cookie_header(value):
                    items.append((key, cookie))
                continue
            items.append((key, value))
        return items

    async def capacitor_handle_async_request(
        self, request: httpx.Request
    ) -> httpx.Response:
        def _should_use_capacitor_http() -> bool:
            host = (request.url.host or "").lower()
            if host.endswith("freedom24.com"):
                return True

            content_type = (
                request.headers.get("content-type")
                or request.headers.get("Content-Type")
                or ""
            ).lower()
            return "multipart/form-data" in content_type

        if not _should_use_capacitor_http():
            return await original_handle_async_request(self, request)

        try:
            CapacitorHttp = js.Capacitor.Plugins.CapacitorHttp
        except AttributeError:
            raise RuntimeError("CapacitorHttp plugin not found in global scope.")

        url_str = str(request.url)
        headers = dict(request.headers)

        headers.pop("accept-encoding", None)
        headers.pop("Accept-Encoding", None)
        headers["Accept-Encoding"] = "identity"

        body_bytes = getattr(request, "content", b"") or b""
        if not body_bytes:
            if hasattr(request.stream, "__aiter__"):
                chunks = []
                async for part in request.stream:
                    chunks.append(part)
                body_bytes = b"".join(chunks)
            elif hasattr(request.stream, "__iter__"):
                chunks = []
                for part in request.stream:
                    chunks.append(part)
                body_bytes = b"".join(chunks)

        if body_bytes:
            headers.pop("Content-Length", None)
            headers.pop("content-length", None)
            headers["Content-Length"] = str(len(body_bytes))

        data_value = (
            body_bytes.decode("utf-8", errors="replace") if body_bytes else None
        )

        options = {
            "url": url_str,
            "method": request.method,
            "headers": headers,
            "responseType": "text",
        }
        if data_value is not None:
            options["data"] = data_value

        timeout = request.extensions.get("timeout", {})
        read_timeout = timeout.get("read")
        if read_timeout is not None and read_timeout > 0:
            ms = int(read_timeout * 1000)
            options["readTimeout"] = ms
            options["connectTimeout"] = ms

        try:
            js_options = to_js(options, create_pyproxies=False)
            response_js = await CapacitorHttp.request(js_options)
        except Exception as e:
            raise httpx.NetworkError(f"Capacitor Native Error: {e}", request=request)

        response_py = response_js.to_py() if hasattr(response_js, "to_py") else {}

        status_code = 0
        try:
            status_code = int(response_py.get("status", 0))
        except Exception:
            status_code = int(getattr(response_js, "status", 0) or 0)

        resp_headers = (
            response_py.get("headers") if isinstance(response_py, dict) else {}
        )
        if hasattr(resp_headers, "to_py"):
            resp_headers = resp_headers.to_py()
        if not isinstance(resp_headers, dict):
            resp_headers = {}
        resp_headers.pop("content-encoding", None)
        resp_headers.pop("Content-Encoding", None)

        raw_data = None
        if isinstance(response_py, dict) and "data" in response_py:
            raw_data = response_py.get("data")
        else:
            raw_data = getattr(response_js, "data", None)

        if hasattr(raw_data, "to_py"):
            raw_data = raw_data.to_py()

        if raw_data is None:
            content = b""
        elif isinstance(raw_data, (bytes, bytearray)):
            content = bytes(raw_data)
        elif isinstance(raw_data, memoryview):
            content = raw_data.tobytes()
        elif isinstance(raw_data, str):
            content = raw_data.encode("utf-8")
        elif isinstance(raw_data, (dict, list, int, float, bool)):
            content = json.dumps(raw_data).encode("utf-8")
        else:
            # Fallback for unexpected JS values.
            content = str(raw_data).encode("utf-8")

        return httpx.Response(
            status_code=status_code,
            headers=_to_httpx_headers(resp_headers),
            content=content,
            request=request,
        )

    httpx.AsyncHTTPTransport.handle_async_request = capacitor_handle_async_request
