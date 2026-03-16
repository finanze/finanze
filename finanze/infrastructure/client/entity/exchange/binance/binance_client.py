import asyncio
import hashlib
import hmac
import logging
import time

from domain.entity_login import EntityLoginResult, LoginResultCode
from infrastructure.client.http.http_session import HttpSession, get_http_session

_MAX_RETRIES = 3
_DEFAULT_RETRY_AFTER = 5


class BinanceClient:
    SPOT_BASE_URL = "https://api.binance.com"
    FUTURES_BASE_URL = "https://fapi.binance.com"

    def __init__(self):
        self._api_key: str = ""
        self._secret_key: str = ""
        self._log = logging.getLogger(__name__)
        self._session: HttpSession = get_http_session()

    def _sign(self, query_string: str) -> str:
        return hmac.new(
            self._secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _auth_headers(self) -> dict:
        return {"X-MBX-APIKEY": self._api_key}

    async def _handle_rate_limit(self, response, attempt: int) -> bool:
        """Handle 429/418 responses. Returns True if should retry."""
        if response.status not in (429, 418) or attempt >= _MAX_RETRIES:
            return False

        retry_after = _DEFAULT_RETRY_AFTER
        raw = response.headers.get("Retry-After")
        if raw:
            try:
                retry_after = int(raw)
            except ValueError:
                pass

        self._log.warning(
            f"Rate limited ({response.status}), waiting {retry_after}s "
            f"(attempt {attempt + 1}/{_MAX_RETRIES})"
        )
        await asyncio.sleep(retry_after)
        return True

    async def _get(self, url: str, headers: dict | None = None):
        for attempt in range(_MAX_RETRIES + 1):
            response = await self._session.get(url, headers=headers)
            if response.ok:
                return await response.json()
            if await self._handle_rate_limit(response, attempt):
                continue
            body = await response.text()
            self._log.error(f"Binance API error ({response.status}): {body}")
            response.raise_for_status()
        return {}

    async def _signed_get(self, base_url: str, path: str, params: dict | None = None):
        for attempt in range(_MAX_RETRIES + 1):
            p = dict(params or {})
            p["timestamp"] = int(time.time() * 1000)
            p["recvWindow"] = 10000
            query_string = "&".join(f"{k}={v}" for k, v in p.items())
            signature = self._sign(query_string)
            url = f"{base_url}{path}?{query_string}&signature={signature}"
            response = await self._session.get(url, headers=self._auth_headers())
            if response.ok:
                return await response.json()
            if await self._handle_rate_limit(response, attempt):
                continue
            body = await response.text()
            self._log.error(f"Binance API error ({response.status}): {body}")
            response.raise_for_status()
        return {}

    async def setup(self, api_key: str, secret_key: str) -> EntityLoginResult:
        self._api_key = api_key
        self._secret_key = secret_key

        try:
            url = f"{self.SPOT_BASE_URL}/api/v3/ping"
            response = await self._session.get(url, headers=self._auth_headers())

            if response.ok:
                return EntityLoginResult(LoginResultCode.CREATED)
            else:
                return EntityLoginResult(
                    LoginResultCode.UNEXPECTED_ERROR,
                    message=f"Unexpected response code {response.status}",
                )
        except Exception as e:
            self._log.error(f"Binance setup error: {e}")
            return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR, message=str(e))

    async def get_spot_account(self) -> dict:
        return await self._signed_get(self.SPOT_BASE_URL, "/api/v3/account")

    async def get_futures_account(self) -> dict:
        return await self._signed_get(self.FUTURES_BASE_URL, "/fapi/v3/account")

    async def get_exchange_info(self) -> dict:
        return await self._get(f"{self.SPOT_BASE_URL}/api/v3/exchangeInfo")

    async def get_my_trades(self, symbol: str, limit: int = 1000) -> list[dict]:
        return await self._signed_get(
            self.SPOT_BASE_URL,
            "/api/v3/myTrades",
            params={"symbol": symbol, "limit": limit},
        )

    async def get_deposit_history(
        self, start_time: int | None = None, end_time: int | None = None
    ) -> list[dict]:
        params = {}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        params["limit"] = 1000
        return await self._signed_get(
            self.SPOT_BASE_URL,
            "/sapi/v1/capital/deposit/hisrec",
            params=params,
        )

    async def get_withdrawal_history(
        self, start_time: int | None = None, end_time: int | None = None
    ) -> list[dict]:
        params = {}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        params["limit"] = 1000
        return await self._signed_get(
            self.SPOT_BASE_URL,
            "/sapi/v1/capital/withdraw/history",
            params=params,
        )
