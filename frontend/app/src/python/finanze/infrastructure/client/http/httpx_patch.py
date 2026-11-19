import json
import math
from typing import Any

import httpx
import js
from pyodide.ffi import JsProxy, to_js


def _is_js_nullish(value: Any) -> bool:
    return value is None or type(value).__name__ in ("JsNull", "JsUndefined")


def _parse_status_code(response_js: Any) -> int:
    raw = (
        response_js.get("status", 0)
        if isinstance(response_js, dict)
        else getattr(response_js, "status", 0)
    )
    if _is_js_nullish(raw):
        return 0
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw) if math.isfinite(raw) else 0
    try:
        parsed = float(str(raw))
        return int(parsed) if math.isfinite(parsed) else 0
    except (TypeError, ValueError, OverflowError):
        return 0


def _extract_headers(response_js: Any) -> dict:
    raw_headers = (
        response_js.get("headers")
        if isinstance(response_js, dict)
        else getattr(response_js, "headers", None)
    )
    if _is_js_nullish(raw_headers):
        return {}
    if isinstance(raw_headers, dict):
        return dict(raw_headers)
    if hasattr(raw_headers, "to_py"):
        try:
            converted = raw_headers.to_py(depth=2)
        except TypeError:
            converted = raw_headers.to_py()
        if isinstance(converted, dict):
            return converted
    return {}


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
        if _is_js_nullish(v):
            continue
        key = str(k)
        if isinstance(v, (list, tuple)):
            for one in v:
                if not _is_js_nullish(one):
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


def _parse_response_data(response_js: Any) -> bytes:
    raw = (
        response_js.get("data")
        if isinstance(response_js, dict)
        else getattr(response_js, "data", None)
    )
    if _is_js_nullish(raw):
        return b""
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    if isinstance(raw, memoryview):
        return raw.tobytes()
    if isinstance(raw, str):
        return raw.encode("utf-8")
    if isinstance(raw, JsProxy):
        if hasattr(raw, "to_bytes"):
            return raw.to_bytes()
        serialized = js.JSON.stringify(raw)
        if _is_js_nullish(serialized):
            return b""
        return str(serialized).encode("utf-8")
    if hasattr(raw, "to_py"):
        raw = raw.to_py()
        if _is_js_nullish(raw):
            return b""
    if isinstance(raw, (dict, list, tuple, int, float, bool)):
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

    status_code = _parse_status_code(response_js)
    resp_headers = _extract_headers(response_js)
    resp_headers.pop("content-encoding", None)
    resp_headers.pop("Content-Encoding", None)

    return httpx.Response(
        status_code=status_code,
        headers=_to_httpx_headers(resp_headers),
        content=_parse_response_data(response_js),
        request=request,
    )


def apply_httpx_patch():
    """Patches httpx to route all requests through Capacitor Native HTTP."""
    httpx.AsyncHTTPTransport.handle_async_request = _capacitor_handle_async_request
