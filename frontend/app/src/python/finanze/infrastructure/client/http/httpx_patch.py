import json

import httpx
import js
from pyodide.ffi import to_js


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
                if one is not None:
                    items.append((key, str(one)))
            continue
        value = str(v)
        if key.lower() == "set-cookie":
            for cookie in _split_set_cookie_header(value):
                items.append((key, cookie))
            continue
        items.append((key, value))
    return items


async def _read_request_body(request: httpx.Request) -> bytes:
    body = getattr(request, "content", b"") or b""
    if body:
        return body
    if hasattr(request.stream, "__aiter__"):
        chunks = [part async for part in request.stream]
        return b"".join(chunks)
    if hasattr(request.stream, "__iter__"):
        return b"".join(request.stream)
    return b""


def _parse_response_data(response_js, response_py: dict) -> bytes:
    raw = response_py.get("data") if isinstance(response_py, dict) else None
    if raw is None:
        raw = getattr(response_js, "data", None)
    if hasattr(raw, "to_py"):
        raw = raw.to_py()
    if raw is None:
        return b""
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    if isinstance(raw, memoryview):
        return raw.tobytes()
    if isinstance(raw, str):
        return raw.encode("utf-8")
    if isinstance(raw, (dict, list, int, float, bool)):
        return json.dumps(raw).encode("utf-8")
    return str(raw).encode("utf-8")


async def _capacitor_handle_async_request(
    self, request: httpx.Request
) -> httpx.Response:
    CapacitorHttp = js.Capacitor.Plugins.CapacitorHttp

    headers = dict(request.headers)
    headers.pop("accept-encoding", None)
    headers.pop("Accept-Encoding", None)
    headers["Accept-Encoding"] = "identity"

    body_bytes = await _read_request_body(request)
    if body_bytes:
        headers.pop("Content-Length", None)
        headers.pop("content-length", None)
        headers["Content-Length"] = str(len(body_bytes))

    options = {
        "url": str(request.url),
        "method": request.method,
        "headers": headers,
        "responseType": "text",
    }
    if body_bytes:
        options["data"] = body_bytes.decode("utf-8", errors="replace")

    timeout = request.extensions.get("timeout", {})
    read_timeout = timeout.get("read")
    if read_timeout and read_timeout > 0:
        ms = int(read_timeout * 1000)
        options["readTimeout"] = ms
        options["connectTimeout"] = ms

    try:
        response_js = await CapacitorHttp.request(
            to_js(options, create_pyproxies=False)
        )
    except Exception as e:
        raise httpx.NetworkError(f"CapacitorHttp error: {e}", request=request)

    response_py = response_js.to_py() if hasattr(response_js, "to_py") else {}

    status_code = int(
        response_py.get("status", 0) or getattr(response_js, "status", 0) or 0
    )

    resp_headers = (
        response_py.get("headers", {}) if isinstance(response_py, dict) else {}
    )
    if hasattr(resp_headers, "to_py"):
        resp_headers = resp_headers.to_py()
    if not isinstance(resp_headers, dict):
        resp_headers = {}
    resp_headers.pop("content-encoding", None)
    resp_headers.pop("Content-Encoding", None)

    return httpx.Response(
        status_code=status_code,
        headers=_to_httpx_headers(resp_headers),
        content=_parse_response_data(response_js, response_py),
        request=request,
    )


def apply_httpx_patch():
    """Patches httpx to route all requests through Capacitor Native HTTP."""
    httpx.AsyncHTTPTransport.handle_async_request = _capacitor_handle_async_request
