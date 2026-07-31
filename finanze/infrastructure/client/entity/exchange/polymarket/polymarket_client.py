import logging
import re
from datetime import datetime, timezone
from typing import Any

from aiocache import cached
from aiocache.serializers import PickleSerializer

from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult, LoginResultCode
from infrastructure.client.http.http_session import HttpSession, get_http_session

_PROFILE_SEARCH_URL = "https://gamma-api.polymarket.com/public-search"
_PUBLIC_PROFILE_URL = "https://gamma-api.polymarket.com/public-profile"
_POSITIONS_URL = "https://data-api.polymarket.com/positions"
_CLOSED_POSITIONS_URL = "https://data-api.polymarket.com/closed-positions"
_ACTIVITY_URL = "https://data-api.polymarket.com/activity"
_TRADES_URL = "https://data-api.polymarket.com/trades"
_USER_PNL_URL = "https://user-pnl-api.polymarket.com/user-pnl"
_POLYGON_BALANCE_TOKENS = [
    {
        "contract": "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb",
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
        return await self._get_collection(_POSITIONS_URL)

    @cached(
        ttl=CLOSED_POSITIONS_CACHE_TTL,
        key_builder=lambda f, self: (
            f"polymarket:closed_positions:{self.wallet_address}"
        ),
        serializer=PickleSerializer(),
    )
    async def get_closed_positions(self) -> list[dict[str, Any]]:
        return await self._get_collection(_CLOSED_POSITIONS_URL)

    async def get_activity(self) -> list[dict[str, Any]]:
        return await self._get_collection(_ACTIVITY_URL)

    async def get_trades(self) -> list[dict[str, Any]]:
        return await self._get_collection(_TRADES_URL)

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
                "user_address": self.wallet_address,
                "interval": interval,
                "fidelity": "1d",
            },
        )
        response.raise_for_status()
        payload = await response.json()
        if isinstance(payload, list):
            return payload
        return []

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

    async def _get_collection(self, url: str) -> list[dict[str, Any]]:
        response = await self._session.get(url, params={"user": self.wallet_address})
        response.raise_for_status()
        payload = await response.json()
        if isinstance(payload, list):
            return payload
        return []

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
