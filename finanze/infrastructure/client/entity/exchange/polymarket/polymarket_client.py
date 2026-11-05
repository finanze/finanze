import logging
import re
from datetime import datetime, timezone
from typing import Any

from aiocache import cached
from aiocache.serializers import PickleSerializer

from domain.constants import PUSD_CONTRACT_ADDRESS
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult, LoginResultCode
from infrastructure.client.http.http_session import HttpSession, get_http_session

_PROFILE_SEARCH_URL = "https://gamma-api.polymarket.com/public-search"
_PUBLIC_PROFILE_URL = "https://gamma-api.polymarket.com/public-profile"
_DATA_API_URL = "https://data-api.polymarket.com/v2"
_POSITIONS_URL = f"{_DATA_API_URL}/positions"
_ACTIVITY_URL = f"{_DATA_API_URL}/activity"
_TRADES_URL = f"{_DATA_API_URL}/trades"
_USER_PNL_URL = f"{_DATA_API_URL}/user-pnl"
_PAGE_LIMIT = 1000
_MAX_PAGES = 100
# v2 floors feeds to three years back unless start=1 is passed
_FULL_HISTORY_START = 1
_OPEN_POSITION_STATUSES = ("OPEN",)
_REDEEMABLE_POSITION_STATUSES = ("REDEEMABLE", "REDEEMABLE_LOST")
_POLYGON_BALANCE_TOKENS = [
    {
        "contract": PUSD_CONTRACT_ADDRESS,
        "symbol": "pUSD",
        "decimals": 6,
    },
    {
        "contract": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "symbol": "USDC",
        "decimals": 6,
    },
    {
        "contract": "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359",
        "symbol": "USDC",
        "decimals": 6,
    },
]
_POLYGON_RPC_ENDPOINTS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://polygon.drpc.org",
    "https://polygon.gateway.tenderly.co",
    "https://1rpc.io/matic",
]
_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
CLOSED_POSITIONS_CACHE_TTL = 60
PNL_CACHE_TTL = 4 * 60 * 60


class PolymarketClient:
    def __init__(self):
        self._session: HttpSession = get_http_session()
        self._log = logging.getLogger(__name__)
        self._wallet_address: str | None = None
        self._identifier: str | None = None
        self._profile: dict[str, Any] | None = None

    async def setup(self, login_params: EntityLoginParams) -> EntityLoginResult:
        identifier = (login_params.credentials.get("identifier") or "").strip()
        if not identifier:
            return EntityLoginResult(
                LoginResultCode.INVALID_CREDENTIALS,
                message="Identifier is required",
            )

        self._identifier = identifier

        try:
            if _ADDRESS_RE.fullmatch(identifier):
                self._wallet_address = identifier.lower()
                profile = await self.get_public_profile(self._wallet_address)
                self._profile = profile if profile else None
            else:
                profile = await self.search_profile(identifier)
                if not profile:
                    return EntityLoginResult(
                        LoginResultCode.INVALID_CREDENTIALS,
                        message="Polymarket profile not found",
                    )
                wallet_address = profile.get("proxyWallet")
                if not wallet_address:
                    return EntityLoginResult(
                        LoginResultCode.CURRENTLY_UNAVAILABLE,
                        message="Polymarket profile has no wallet address",
                    )
                self._wallet_address = str(wallet_address).lower()
                self._profile = profile

            return EntityLoginResult(LoginResultCode.CREATED)
        except Exception as e:
            self._log.error(f"Polymarket setup error: {e}")
            return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR, message=str(e))

    @property
    def wallet_address(self) -> str:
        if not self._wallet_address:
            raise RuntimeError("Polymarket client not initialized")
        return self._wallet_address

    @property
    def profile(self) -> dict[str, Any] | None:
        return self._profile

    async def search_profile(self, query: str) -> dict[str, Any] | None:
        response = await self._session.get(
            _PROFILE_SEARCH_URL,
            params={"q": query, "search_profiles": "true"},
        )
        response.raise_for_status()
        payload = await response.json()
        profiles = payload.get("profiles") or []
        if not profiles:
            return None

        query_lower = query.strip().lower()

        def _score(profile: dict[str, Any]) -> tuple[int, int]:
            name = str(profile.get("name") or "").strip().lower()
            pseudonym = str(profile.get("pseudonym") or "").strip().lower()
            if name == query_lower:
                return (0, len(name))
            if pseudonym == query_lower:
                return (1, len(pseudonym))
            if name.startswith(query_lower):
                return (2, len(name))
            if pseudonym.startswith(query_lower):
                return (3, len(pseudonym))
            return (4, len(name or pseudonym or query_lower))

        return min(profiles, key=_score)

    async def get_public_profile(self, address: str) -> dict[str, Any] | None:
        response = await self._session.get(
            _PUBLIC_PROFILE_URL,
            params={"address": address},
        )
        response.raise_for_status()
        payload = await response.json()
        if isinstance(payload, dict) and payload:
            return payload
        return None

    async def get_positions(self) -> list[dict[str, Any]]:
        """Open positions plus resolved ones still pending redemption.

        Rows are normalized to the v1 field names (``redeemable`` is True for
        resolved positions), which the fetcher relies on.
        """
        positions: list[dict[str, Any]] = []
        for status in _OPEN_POSITION_STATUSES + _REDEEMABLE_POSITION_STATUSES:
            rows = await self._get_collection(_POSITIONS_URL, {"status": status})
            positions.extend(self._normalize_position(row) for row in rows)
        return positions

    @cached(
        ttl=CLOSED_POSITIONS_CACHE_TTL,
        key_builder=lambda f, self: (
            f"polymarket:closed_positions:{self.wallet_address}"
        ),
        serializer=PickleSerializer(),
    )
    async def get_closed_positions(self) -> list[dict[str, Any]]:
        rows = await self._get_collection(_POSITIONS_URL, {"status": "CLOSED"})
        return [self._normalize_closed_position(row) for row in rows]

    async def get_activity(self) -> list[dict[str, Any]]:
        rows = await self._get_collection(_ACTIVITY_URL, {"start": _FULL_HISTORY_START})
        return [self._normalize_trade(row) for row in rows]

    async def get_trades(self) -> list[dict[str, Any]]:
        rows = await self._get_collection(_TRADES_URL, {"start": _FULL_HISTORY_START})
        return [self._normalize_trade(row) for row in rows]

    @cached(
        ttl=PNL_CACHE_TTL,
        key_builder=lambda f, self, interval="all", **kwargs: (
            f"polymarket:pnl:{self.wallet_address}:{interval}"
        ),
        serializer=PickleSerializer(),
    )
    async def get_user_pnl(self, interval: str = "all") -> list[dict[str, Any]]:
        response = await self._session.get(
            _USER_PNL_URL,
            params={
                "user": self.wallet_address,
                "interval": interval,
                "fidelity": "1d",
            },
        )
        response.raise_for_status()
        payload = await response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        points = data.get("points") if isinstance(data, dict) else None
        if not isinstance(points, list):
            return []
        # trade_pnl is the series v1 exposed as "p"
        return [
            {"t": point["timestamp"], "p": point["trade_pnl"]}
            for point in points
            if point.get("timestamp") is not None and point.get("trade_pnl") is not None
        ]

    async def get_available_balance(self) -> tuple[Dezimal, str]:
        wallet = self.wallet_address
        successful_zero_balance: tuple[Dezimal, str] | None = None
        fallback_symbol = _POLYGON_BALANCE_TOKENS[0]["symbol"]

        for token in _POLYGON_BALANCE_TOKENS:
            contract = token["contract"]
            symbol = token["symbol"]
            decimals = token["decimals"]
            for rpc_url in _POLYGON_RPC_ENDPOINTS:
                try:
                    balance = await self._get_erc20_balance(
                        rpc_url, contract, wallet, decimals
                    )
                    if balance is None:
                        continue
                    if balance != 0:
                        return balance, symbol
                    if successful_zero_balance is None:
                        successful_zero_balance = (balance, symbol)
                    break
                except Exception as e:
                    self._log.debug(
                        "Polymarket balance lookup failed for %s via %s: %s",
                        contract,
                        rpc_url,
                        e,
                    )

        if successful_zero_balance is not None:
            return successful_zero_balance
        return Dezimal(0), fallback_symbol

    async def _get_collection(
        self, url: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        base_params = {"user": self.wallet_address, **(params or {})}
        rows: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(_MAX_PAGES):
            # Filters must be repeated on every page; limit only applies to the
            # first one (the cursor carries the page size afterwards).
            page_params = (
                {**base_params, "cursor": cursor}
                if cursor
                else {**base_params, "limit": _PAGE_LIMIT}
            )
            response = await self._session.get(url, params=page_params)
            response.raise_for_status()
            payload = await response.json()
            if not isinstance(payload, dict):
                break
            data = payload.get("data")
            if isinstance(data, list):
                rows.extend(data)
            pagination = payload.get("pagination") or {}
            cursor = pagination.get("next_cursor")
            if not cursor:
                break
        else:
            self._log.warning("Polymarket pagination limit reached for %s", url)
        return rows

    @staticmethod
    def _normalize_common(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "conditionId": row.get("condition_id"),
            "asset": row.get("token_id"),
            "title": row.get("title"),
            "slug": row.get("slug"),
            "eventSlug": row.get("event_slug"),
            "icon": row.get("icon"),
            "outcome": row.get("outcome"),
            "outcomeIndex": row.get("outcome_index"),
        }

    @classmethod
    def _normalize_position(cls, row: dict[str, Any]) -> dict[str, Any]:
        status = row.get("status")
        return {
            **cls._normalize_common(row),
            "size": row.get("current_size"),
            "avgPrice": row.get("avg_price"),
            "initialValue": row.get("entry_cost_usdc"),
            "currentValue": row.get("current_value"),
            "cashPnl": row.get("unrealized_pnl"),
            "percentPnl": row.get("percent_pnl"),
            "realizedPnl": row.get("realized_pnl"),
            "totalBought": row.get("total_size"),
            "curPrice": row.get("current_price"),
            "endDate": row.get("end_date"),
            "timestamp": row.get("last_event_at"),
            "status": status,
            "redeemable": status in _REDEEMABLE_POSITION_STATUSES
            or row.get("redeemable") is True,
            "mergeable": row.get("mergeable"),
            "negativeRisk": row.get("negative_risk"),
        }

    @classmethod
    def _normalize_closed_position(cls, row: dict[str, Any]) -> dict[str, Any]:
        # Closed rows report zeroed current-holding fields; keep only the
        # lifetime economics, as the v1 closed-positions endpoint did.
        return {
            **cls._normalize_common(row),
            "avgPrice": row.get("avg_price"),
            "totalBought": row.get("total_size"),
            "realizedPnl": row.get("realized_pnl"),
            "curPrice": row.get("current_price"),
            "endDate": row.get("end_date"),
            "timestamp": row.get("last_event_at"),
            "status": row.get("status"),
        }

    @classmethod
    def _normalize_trade(cls, row: dict[str, Any]) -> dict[str, Any]:
        return {
            **cls._normalize_common(row),
            "type": row.get("type"),
            "side": row.get("side"),
            "size": row.get("size"),
            "usdcSize": row.get("usdc_size"),
            "price": row.get("price"),
            "timestamp": row.get("timestamp"),
            "transactionHash": row.get("transaction_hash"),
        }

    async def _get_erc20_balance(
        self,
        rpc_url: str,
        contract_address: str,
        wallet_address: str,
        decimals: int,
    ) -> Dezimal | None:
        balance_call = f"0x70a08231{'0' * 24}{wallet_address[2:].lower()}"
        response = await self._session.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_call",
                "params": [
                    {
                        "to": contract_address,
                        "data": balance_call,
                    },
                    "latest",
                ],
            },
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        payload = await response.json()
        if not isinstance(payload, dict):
            return None

        result = payload.get("result")
        if not isinstance(result, str) or not result.startswith("0x"):
            return None

        return Dezimal(int(result, 16)) / Dezimal(10**decimals)

    @staticmethod
    def parse_timestamp(value: Any) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        text = str(value).strip()
        if not text:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        except ValueError:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
