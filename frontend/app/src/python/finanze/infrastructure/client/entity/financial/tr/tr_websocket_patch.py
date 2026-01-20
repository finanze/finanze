import asyncio
import json
import logging
from typing import Any, Optional

import js
from pyodide.ffi import create_proxy, to_js

from infrastructure.client.entity.financial.tr import api as tr_api

_log = logging.getLogger(__name__)


def apply_traderepublic_websocket_patch() -> None:
    class _BrowserWebSocket:
        def __init__(self, url: str):
            self._url = url
            self._ws = None
            self._incoming: "asyncio.Queue[str]" = asyncio.Queue()
            self.close_code: Optional[int] = None
            self._open_fut: Optional[asyncio.Future[None]] = None
            self._error: Optional[BaseException] = None
            self._on_open_proxy = None
            self._on_message_proxy = None
            self._on_error_proxy = None
            self._on_close_proxy = None

        async def connect(self) -> "_BrowserWebSocket":
            if self._ws is not None and self.close_code is None:
                return self

            loop = asyncio.get_running_loop()
            self._open_fut = loop.create_future()
            self._error = None
            self.close_code = None
            self._ws = js.WebSocket.new(self._url)

            def _to_str(data: Any) -> str:
                try:
                    return data.to_py()
                except Exception:
                    return str(data)

            def _on_open(_event):
                if self._open_fut is not None and not self._open_fut.done():
                    self._open_fut.set_result(None)

            def _on_message(event):
                payload = _to_str(event.data)
                self._incoming.put_nowait(payload)

            def _on_error(_event):
                self._error = RuntimeError("WebSocket error")
                if self._open_fut is not None and not self._open_fut.done():
                    self._open_fut.set_exception(self._error)

            def _on_close(event):
                try:
                    self.close_code = int(event.code)
                except Exception:
                    self.close_code = 1006
                self._incoming.put_nowait("")

            self._on_open_proxy = create_proxy(_on_open)
            self._on_message_proxy = create_proxy(_on_message)
            self._on_error_proxy = create_proxy(_on_error)
            self._on_close_proxy = create_proxy(_on_close)

            self._ws.onopen = self._on_open_proxy
            self._ws.onmessage = self._on_message_proxy
            self._ws.onerror = self._on_error_proxy
            self._ws.onclose = self._on_close_proxy

            await self._open_fut
            return self

        async def send(self, data: str) -> None:
            await self.connect()
            if self._ws is None:
                raise RuntimeError("WebSocket not connected")
            self._ws.send(data)

        async def recv(self) -> str:
            msg = await self._incoming.get()
            if self.close_code is not None:
                if self._error is not None:
                    raise self._error
                raise RuntimeError("WebSocket closed")
            return msg

        async def close(self) -> None:
            if self._ws is None:
                self.close_code = 1006
                return
            try:
                self._ws.close()
            finally:
                if self.close_code is None:
                    self.close_code = 1000

    original_subscribe = tr_api.TradeRepublicApi.subscribe

    def _get_native_cookies_plugin():
        try:
            plugin = getattr(js.window, "NativeCookies", None)
            if plugin is not None:
                return plugin
        except Exception:
            pass

        try:
            return js.Capacitor.Plugins.NativeCookies
        except Exception:
            return None

    async def _sync_native_cookies_to_httpx(tr_api_self) -> None:
        plugin = _get_native_cookies_plugin()
        if plugin is None:
            return

        async def _sync(url: str, domain: str) -> None:
            try:
                res = await plugin.getAllCookies(
                    to_js({"url": url}, create_pyproxies=False)
                )
                res_py = res.to_py() if hasattr(res, "to_py") else res
                cookies = res_py.get("cookies") if isinstance(res_py, dict) else None
                if not isinstance(cookies, dict):
                    return
                for name, value in cookies.items():
                    if not name or value is None:
                        continue
                    tr_api_self._websession.cookies.set(
                        str(name), str(value), domain=domain, path="/"
                    )
            except Exception as e:
                _log.error(f"[TR WS] NativeCookies.getAllCookies failed: {e}")

        await _sync("https://traderepublic.com", ".traderepublic.com")
        await _sync("https://api.traderepublic.com", "api.traderepublic.com")

        try:
            res = await plugin.getCookie(
                to_js(
                    {"url": "https://api.traderepublic.com", "name": "tr_session"},
                    create_pyproxies=False,
                )
            )
            res_py = res.to_py() if hasattr(res, "to_py") else res
            value = res_py.get("value") if isinstance(res_py, dict) else None
            if value:
                tr_api_self._websession.cookies.set(
                    "tr_session", str(value), domain=".traderepublic.com", path="/"
                )
                tr_api_self._websession.cookies.set(
                    "tr_session",
                    str(value),
                    domain="api.traderepublic.com",
                    path="/",
                )
        except Exception as e:
            _log.error(f"[TR WS] NativeCookies.getCookie failed: {e}")

    async def _get_weblogin_token() -> Optional[str]:
        plugin = _get_native_cookies_plugin()
        if plugin is None:
            return None

        try:
            result = await plugin.getCookie(
                to_js(
                    {"url": "https://api.traderepublic.com", "name": "tr_session"},
                    create_pyproxies=False,
                )
            )
            result_py = result.to_py() if hasattr(result, "to_py") else result
            if isinstance(result_py, dict) and result_py.get("value"):
                return str(result_py["value"])
        except Exception as e:
            _log.error(f"[TR WS] NativeCookies.getCookie failed: {e}")

        return None

    async def _get_ws_pyodide(self):
        if getattr(self, "_ws", None) is not None and self._ws.close_code is None:
            return self._ws

        self.log.info("Connecting to websocket...")

        connection_message = {"locale": self._locale}
        connect_id = 21

        if getattr(self, "_weblogin", False):
            connection_message = {
                "locale": self._locale,
                "platformId": "webtrading",
                "platformVersion": "chrome - 94.0.4606",
                "clientId": "app.traderepublic.com",
                "clientVersion": "5582",
            }
            connect_id = 31

        if getattr(self, "_weblogin", False):
            await _sync_native_cookies_to_httpx(self)

        self._ws = await _BrowserWebSocket("wss://api.traderepublic.com").connect()

        await self._ws.send(f"connect {connect_id} {json.dumps(connection_message)}")
        response = await self._ws.recv()

        if response != "connected":
            raise ValueError(f"Connection Error: {response}")

        self.log.info("Connected to websocket...")
        return self._ws

    async def _subscribe_pyodide(self, payload):
        if not getattr(self, "_weblogin", False):
            return await original_subscribe(self, payload)

        await _sync_native_cookies_to_httpx(self)

        subscription_id = await self._next_subscription_id()
        ws = await self._get_ws()
        self.log.debug(f"Subscribing: 'sub {subscription_id} {json.dumps(payload)}'")
        self.subscriptions[subscription_id] = payload

        payload_with_token = payload.copy() if isinstance(payload, dict) else payload

        if isinstance(payload_with_token, dict) and "token" not in payload_with_token:
            token = await _get_weblogin_token()
            if token:
                payload_with_token["token"] = token
            else:
                _log.warning(
                    "[TR WS] No token found, sending subscription without token"
                )

        await ws.send(f"sub {subscription_id} {json.dumps(payload_with_token)}")
        return subscription_id

    tr_api.TradeRepublicApi._get_ws = _get_ws_pyodide
    tr_api.TradeRepublicApi.subscribe = _subscribe_pyodide
