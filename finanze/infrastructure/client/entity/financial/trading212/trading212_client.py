import asyncio
import base64
import logging
import random
import time
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import httpx
from aiocache import Cache, cached

from domain.entity_login import EntityLoginResult, LoginResultCode
from infrastructure.client.http.http_session import new_http_session

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_BACKOFF_FACTOR = 2.0
_PAGE_LIMIT = 50
_REQUEST_TIMEOUT = 30.0
_SUMMARY_TTL = 30.0


class Trading212Client:
    BASE_URL = "https://demo.trading212.com"

    def __init__(self):
        self._headers: dict[str, str] = {}
        self._log = logging.getLogger(__name__)
        self._session = new_http_session(timeout=_REQUEST_TIMEOUT)
        self._account_summary: dict | None = None
        self._account_summary_at: float = 0.0

    def _set_auth(self, api_key: str, secret_key: str) -> None:
        credentials = f"{api_key}:{secret_key}".encode("utf-8")
        encoded = base64.b64encode(credentials).decode("utf-8")
        self._headers = {"Authorization": f"Basic {encoded}"}

    @staticmethod
    def _header(headers: dict, name: str) -> str | None:
        target = name.lower()
        for key, value in headers.items():
            if key.lower() == target:
                return value
        return None

    def _retry_delay(self, response, attempt: int) -> float:
        delay = _BACKOFF_FACTOR * (_BACKOFF_BASE**attempt) + random.uniform(
            0, _BACKOFF_FACTOR
        )
        header_wait: float | None = None
        raw_retry = self._header(response.headers, "Retry-After")
        raw_reset = self._header(response.headers, "x-ratelimit-reset")
        if raw_retry:
            try:
                header_wait = float(int(raw_retry))
            except ValueError:
                pass
        elif raw_reset:
            try:
                header_wait = float(int(raw_reset) - int(time.time()))
            except ValueError:
                pass
        if header_wait is not None and header_wait > 0:
            delay = max(delay, header_wait)
        return delay

    async def _handle_rate_limit(self, response, attempt: int) -> bool:
        if response.status != 429 or attempt >= _MAX_RETRIES:
            return False

        delay = self._retry_delay(response, attempt)
        self._log.warning(
            f"Trading 212 rate limited, waiting {delay:.2f}s "
            f"(attempt {attempt + 1}/{_MAX_RETRIES})"
        )
        await asyncio.sleep(delay)
        return True

    async def _get(self, path: str, timeout: float | None = None):
        url = path if path.startswith("http") else self.BASE_URL + path
        for attempt in range(_MAX_RETRIES + 1):
            kwargs = {"headers": self._headers}
            if timeout is not None:
                kwargs["timeout"] = timeout
            response = await self._session.get(url, **kwargs)
            if response.ok:
                return await response.json()
            if await self._handle_rate_limit(response, attempt):
                continue
            body = await response.text()
            self._log.error(f"Trading 212 API error ({response.status}): {body}")
            response.raise_for_status()
        return {}

    @staticmethod
    def _to_path(next_page: str | None) -> str | None:
        if not next_page:
            return None
        if next_page.startswith("http"):
            parsed = urlparse(next_page)
            query = f"?{parsed.query}" if parsed.query else ""
            return f"{parsed.path}{query}"
        return next_page

    async def iter_pages(self, path: str) -> AsyncIterator[list[dict]]:
        separator = "&" if "?" in path else "?"
        next_path: str | None = f"{path}{separator}limit={_PAGE_LIMIT}"
        while next_path:
            data = await self._get(next_path)
            if not isinstance(data, dict):
                return
            items = data.get("items") or []
            yield items
            next_path = self._to_path(data.get("nextPagePath"))

    async def setup(
        self, api_key: str | None, secret_key: str | None
    ) -> EntityLoginResult:
        if not api_key or not secret_key:
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

        self._set_auth(api_key, secret_key)
        self._account_summary = None
        self._account_summary_at = 0.0
        try:
            await self.get_account_summary()
            return EntityLoginResult(LoginResultCode.CREATED)
        except httpx.HTTPStatusError as e:
            self._log.error(f"Trading 212 setup error: {e}")
            if e.response.status_code in (401, 403):
                return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
            return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR, message=str(e))
        except Exception as e:
            self._log.error(f"Trading 212 setup error: {e}")
            return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR, message=str(e))

    async def get_account_summary(self) -> dict:
        now = time.monotonic()
        if (
            self._account_summary is not None
            and now - self._account_summary_at < _SUMMARY_TTL
        ):
            return self._account_summary
        result = await self._get("/api/v0/equity/account/summary")
        summary = result if isinstance(result, dict) else {}
        self._account_summary = summary
        self._account_summary_at = now
        return summary

    async def get_positions(self) -> list[dict]:
        result = await self._get("/api/v0/equity/positions")
        return result if isinstance(result, list) else []

    @cached(cache=Cache.MEMORY, ttl=86400, noself=True)
    async def get_instruments(self) -> list[dict]:
        result = await self._get("/api/v0/equity/metadata/instruments")
        return result if isinstance(result, list) else []

    async def iter_history_orders(self) -> AsyncIterator[list[dict]]:
        async for page in self.iter_pages("/api/v0/equity/history/orders"):
            yield page

    async def iter_history_dividends(self) -> AsyncIterator[list[dict]]:
        async for page in self.iter_pages("/api/v0/equity/history/dividends"):
            yield page

    async def iter_history_transactions(self) -> AsyncIterator[list[dict]]:
        async for page in self.iter_pages("/api/v0/equity/history/transactions"):
            yield page
