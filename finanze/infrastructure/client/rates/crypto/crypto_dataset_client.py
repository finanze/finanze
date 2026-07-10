import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from domain.dezimal import Dezimal
from infrastructure.client.http.http_session import get_http_session
from infrastructure.client.rates.crypto.crypto_dataset_store import (
    CryptoDatasetStore,
)


@dataclass
class CryptoDatasetPlatform:
    provider_id: str
    name: str
    icon_url: Optional[str]


@dataclass
class CryptoDatasetCoin:
    id: str
    symbol: str
    name: str
    icon_url: Optional[str]
    platforms: dict[str, str]
    prices: dict[str, Dezimal]


class CryptoDataset:
    def __init__(
        self,
        updated_at: datetime,
        coins: list[CryptoDatasetCoin],
        platforms: dict[str, CryptoDatasetPlatform],
    ):
        self.updated_at = updated_at
        self.coins = coins
        self.platforms = platforms
        self._by_id: dict[str, CryptoDatasetCoin] = {}
        self._by_symbol: dict[str, list[CryptoDatasetCoin]] = {}
        self._by_address: dict[str, CryptoDatasetCoin] = {}
        for coin in coins:
            self._by_id.setdefault(coin.id, coin)
            self._by_symbol.setdefault(coin.symbol.upper(), []).append(coin)
            for address in coin.platforms.values():
                if address:
                    self._by_address.setdefault(address.strip().lower(), coin)

    def coin_by_id(self, coin_id: str) -> Optional[CryptoDatasetCoin]:
        return self._by_id.get(coin_id)

    def coins_by_symbol(self, symbol: str) -> list[CryptoDatasetCoin]:
        return self._by_symbol.get(symbol.strip().upper(), [])

    def coin_by_address(self, address: str) -> Optional[CryptoDatasetCoin]:
        return self._by_address.get(address.strip().lower())

    def to_coingecko_coin_list(self) -> list[dict[str, Any]]:
        return [
            {
                "id": coin.id,
                "symbol": coin.symbol,
                "name": coin.name,
                "platforms": dict(coin.platforms),
            }
            for coin in self.coins
        ]

    def to_coingecko_platforms(self) -> list[dict[str, Any]]:
        return [
            {
                "id": platform.provider_id,
                "name": platform.name,
                "image": {"large": platform.icon_url} if platform.icon_url else {},
            }
            for platform in self.platforms.values()
        ]

    def prices_by_symbols(
        self, symbols: list[str], fiats: list[str]
    ) -> dict[str, dict[str, Dezimal]]:
        wanted = [fiat.upper() for fiat in fiats]
        result: dict[str, dict[str, Dezimal]] = {}
        for symbol in symbols:
            coin = self._first_priced(self.coins_by_symbol(symbol))
            if coin is None:
                continue
            prices = {cur: coin.prices[cur] for cur in wanted if cur in coin.prices}
            if prices:
                result[symbol.strip().upper()] = prices
        return result

    def prices_by_addresses(
        self, addresses: list[str], fiats: list[str]
    ) -> dict[str, dict[str, Dezimal]]:
        wanted = [fiat.upper() for fiat in fiats]
        result: dict[str, dict[str, Dezimal]] = {}
        for raw in addresses:
            if not isinstance(raw, str):
                continue
            coin = self.coin_by_address(raw)
            if coin is None:
                continue
            prices = {cur: coin.prices[cur] for cur in wanted if cur in coin.prices}
            if prices:
                result[raw.strip().lower()] = prices
        return result

    @staticmethod
    def _first_priced(
        coins: list[CryptoDatasetCoin],
    ) -> Optional[CryptoDatasetCoin]:
        for coin in coins:
            if coin.prices:
                return coin
        return None


class CryptoDatasetClient:
    BASE_URL = os.getenv("CRYPTO_DATASET_URL") or "https://static.finanze.me/crypto/v1"
    TIMEOUT = 10

    # Structural data (coin list, platforms) barely changes, so a stale local copy
    # is acceptable for days. Prices, however, are only served as a catastrophic
    # fallback (live providers down) and want to be reasonably fresh.
    LIST_MAX_AGE = timedelta(days=5)
    PRICE_MAX_AGE = timedelta(hours=6)
    # Guards against hammering the static endpoint when the upstream snapshot itself
    # has not been refreshed yet (its updated_at stays stale between publishes).
    REFRESH_COOLDOWN = timedelta(hours=1)

    COINGECKO = "cg"
    COINMARKETCAP = "cmc"

    def __init__(self, store: Optional[CryptoDatasetStore] = None):
        self._log = logging.getLogger(__name__)
        self._session = get_http_session()
        self._store = store
        self._datasets: dict[str, CryptoDataset] = {}
        self._last_attempt: dict[str, datetime] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def load_coingecko(
        self, max_age: timedelta = LIST_MAX_AGE, **kwargs
    ) -> Optional[CryptoDataset]:
        return await self._load(self.COINGECKO, max_age, **kwargs)

    async def load_coinmarketcap(
        self, max_age: timedelta = LIST_MAX_AGE, **kwargs
    ) -> Optional[CryptoDataset]:
        return await self._load(self.COINMARKETCAP, max_age, **kwargs)

    async def _load(
        self, dataset_key: str, max_age: timedelta, **kwargs
    ) -> Optional[CryptoDataset]:
        cached = self._datasets.get(dataset_key)
        if cached is not None and self._is_fresh(cached, max_age):
            return cached

        if cached is None:
            stored = await self._load_from_store(dataset_key)
            if stored is not None:
                self._datasets[dataset_key] = stored
                cached = stored
                if self._is_fresh(stored, max_age):
                    return stored

        return await self._refresh(dataset_key, max_age, cached, **kwargs)

    async def _refresh(
        self,
        dataset_key: str,
        max_age: timedelta,
        current: Optional["CryptoDataset"],
        **kwargs,
    ) -> Optional["CryptoDataset"]:
        lock = self._locks.setdefault(dataset_key, asyncio.Lock())
        async with lock:
            # Re-check after acquiring the lock: a concurrent refresh may have
            # already produced a fresh dataset.
            latest = self._datasets.get(dataset_key, current)
            if latest is not None and self._is_fresh(latest, max_age):
                return latest

            if not self._cooldown_elapsed(dataset_key):
                return latest

            self._last_attempt[dataset_key] = datetime.now(timezone.utc)
            raw = await self._fetch_remote(dataset_key, **kwargs)
            if raw is not None:
                dataset = self._build(raw)
                if dataset is not None:
                    self._datasets[dataset_key] = dataset
                    await self._persist(dataset_key, raw)
                    return dataset

            return self._datasets.get(dataset_key, latest)

    @staticmethod
    def _is_fresh(dataset: "CryptoDataset", max_age: timedelta) -> bool:
        return datetime.now(timezone.utc) - dataset.updated_at < max_age

    def _cooldown_elapsed(self, dataset_key: str) -> bool:
        last = self._last_attempt.get(dataset_key)
        if last is None:
            return True
        return datetime.now(timezone.utc) - last >= self.REFRESH_COOLDOWN

    async def _fetch_remote(self, dataset_key: str, **kwargs) -> Optional[Any]:
        url = f"{self.BASE_URL}/{dataset_key}/list.json"
        try:
            response = await self._session.get(
                url, timeout=kwargs.get("timeout") or self.TIMEOUT
            )
            if not response.ok:
                body = await response.text()
                self._log.error(
                    f"Error fetching crypto dataset {dataset_key}: "
                    f"{response.status} {body[:200]}"
                )
                return None
            return await response.json()
        except (httpx.RequestError, TimeoutError) as e:
            self._log.error(f"Failed fetching crypto dataset {dataset_key}: {e}")
            return None
        except ValueError as e:
            self._log.error(f"Failed decoding crypto dataset {dataset_key}: {e}")
            return None

    async def _persist(self, dataset_key: str, raw: Any) -> None:
        if self._store is None:
            return
        try:
            await self._store.save(dataset_key, json.dumps(raw))
        except Exception as e:
            self._log.warning(f"Failed to persist crypto dataset {dataset_key}: {e}")

    async def _load_from_store(self, dataset_key: str) -> Optional[CryptoDataset]:
        if self._store is None:
            return None
        try:
            raw_text = await self._store.load(dataset_key)
        except Exception as e:
            self._log.warning(
                f"Failed to load crypto dataset {dataset_key} from store: {e}"
            )
            return None
        if not raw_text:
            return None
        try:
            raw = json.loads(raw_text)
        except Exception as e:
            self._log.warning(
                f"Failed to decode stored crypto dataset {dataset_key}: {e}"
            )
            return None
        return self._build(raw)

    def _build(self, raw: Any) -> Optional[CryptoDataset]:
        if not isinstance(raw, dict):
            return None

        coins_raw = raw.get("coins")
        if not isinstance(coins_raw, list) or not coins_raw:
            return None

        coin_icon_base = raw.get("coin_icon_base") or ""
        platform_icon_base = raw.get("platform_icon_base") or ""
        updated_at = self._parse_updated_at(raw.get("updated_at"))

        coins: list[CryptoDatasetCoin] = []
        for entry in coins_raw:
            coin = self._build_coin(entry, coin_icon_base)
            if coin is not None:
                coins.append(coin)
        if not coins:
            return None

        platforms: dict[str, CryptoDatasetPlatform] = {}
        platforms_raw = raw.get("platforms")
        if isinstance(platforms_raw, dict):
            for platform_id, platform_data in platforms_raw.items():
                if not platform_id or not isinstance(platform_data, dict):
                    continue
                name = platform_data.get("n") or platform_id
                icon_url = self._expand_icon(
                    platform_data.get("ic"), platform_icon_base
                )
                platforms[platform_id] = CryptoDatasetPlatform(
                    provider_id=platform_id, name=name, icon_url=icon_url
                )

        return CryptoDataset(updated_at=updated_at, coins=coins, platforms=platforms)

    def _build_coin(
        self, entry: Any, coin_icon_base: str
    ) -> Optional[CryptoDatasetCoin]:
        if not isinstance(entry, dict):
            return None
        raw_id = entry.get("i")
        symbol = entry.get("s")
        name = entry.get("n")
        if raw_id is None or not symbol or not name:
            return None

        platforms: dict[str, str] = {}
        raw_platforms = entry.get("pt")
        if isinstance(raw_platforms, dict):
            for platform_id, address in raw_platforms.items():
                if platform_id and isinstance(address, str) and address.strip():
                    platforms[platform_id] = address.strip()

        prices: dict[str, Dezimal] = {}
        raw_prices = entry.get("p")
        if isinstance(raw_prices, dict):
            for fiat, value in raw_prices.items():
                try:
                    prices[fiat.upper()] = Dezimal(value)
                except Exception:
                    continue

        return CryptoDatasetCoin(
            id=str(raw_id),
            symbol=str(symbol),
            name=str(name),
            icon_url=self._expand_icon(entry.get("ic"), coin_icon_base),
            platforms=platforms,
            prices=prices,
        )

    @staticmethod
    def _expand_icon(icon: Any, base: str) -> Optional[str]:
        if not icon or not isinstance(icon, str):
            return None
        if base:
            return f"{base}{icon}"
        return icon

    @staticmethod
    def _parse_updated_at(raw: Any) -> datetime:
        if isinstance(raw, str) and raw:
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except Exception:
                pass
        return datetime.now(timezone.utc)
