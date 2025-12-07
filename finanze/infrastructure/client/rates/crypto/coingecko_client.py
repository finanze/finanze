import logging
from typing import Any, Callable

import requests
from cachetools import TTLCache, cached
from domain.crypto import CryptoAsset
from domain.dezimal import Dezimal
from domain.exception.exceptions import (
    InvalidProvidedCredentials,
    MissingFieldsError,
    TooManyRequests,
)
from domain.native_entities import BSC, ETHEREUM, TRON
from infrastructure.client.http.backoff import http_get_with_backoff


class CoinGeckoClient:
    BASE_URL = "https://api.coingecko.com/api/v3"
    TIMEOUT = 10
    CHUNK_SIZE = 50
    COOLDOWN = 1
    MAX_RETRIES = 4
    BACKOFF_EXPONENT_BASE = 2.8
    BACKOFF_FACTOR = 1.6

    ENTITY_CHAIN_MAP = {
        ETHEREUM: "ethereum",
        BSC: "binance-smart-chain",
        TRON: "tron",
    }

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def search(self, query: str) -> list[CryptoAsset]:
        if not query or not query.strip():
            raise MissingFieldsError(["query"])
        data = self._fetch("/search", params={"query": query.strip()})
        coins = data.get("coins", [])
        return self._map_search_results(coins)

    @cached(
        cache=TTLCache(maxsize=1, ttl=86400),
    )
    def get_coin_list(self) -> list[dict[str, Any]]:
        params = {"include_platform": "true"}
        data = self._fetch("/coins/list", params=params, timeout=self.TIMEOUT)
        if not isinstance(data, list):
            self._log.warning(
                f"Unexpected response for /coins/list, expected list. Got type {type(data)}"
            )
            return []

        return data

    @cached(cache=TTLCache(maxsize=1, ttl=86400))
    def _get_coin_address_index(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        try:
            coin_list = self.get_coin_list()
        except Exception as e:
            self._log.error(f"Failed to fetch coin list for address overview: {e}")
            return index
        for coin in coin_list:
            self._add_platform_addresses(index, coin)
        return index

    def _add_platform_addresses(
        self, index: dict[str, dict[str, Any]], coin: dict[str, Any]
    ) -> None:
        try:
            coin_id = coin.get("id")
            if not coin_id:
                return
            platforms = coin.get("platforms") or {}
            if not isinstance(platforms, dict):
                return
            symbol = (coin.get("symbol") or "").upper() or None
            for _, addr in platforms.items():
                if not isinstance(addr, str):
                    continue
                normalized = addr.strip().lower()
                if not normalized or normalized in index:
                    continue
                index[normalized] = {
                    "id": coin_id,
                    "symbol": symbol,
                    "name": coin.get("name"),
                }
        except Exception:
            return

    def get_coin_overview_by_addresses(
        self, addresses: list[str]
    ) -> dict[str, dict[str, Any]]:
        if not addresses:
            return {}
        index = self._get_coin_address_index()
        result: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for raw in addresses:
            if not isinstance(raw, str):
                continue
            addr = raw.strip().lower()
            if not addr or addr in seen:
                continue
            seen.add(addr)
            coin = index.get(addr)
            if coin:
                result[addr] = coin
        return result

    def get_prices_by_addresses(
        self,
        addresses: list[str],
        vs_currencies: list[str],
        timeout: int = TIMEOUT,
    ) -> dict[str, dict[str, Dezimal]]:
        if not addresses:
            return {}
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in addresses:
            if not isinstance(raw, str):
                continue
            addr = raw.strip().lower()
            if not addr or addr in seen:
                continue
            seen.add(addr)
            normalized.append(addr)
        if not normalized:
            return {}
        overview = self.get_coin_overview_by_addresses(normalized)
        id_to_addresses: dict[str, list[str]] = {}
        for addr in normalized:
            coin = overview.get(addr)
            coin_id = coin.get("id") if coin else None
            if not coin_id:
                continue
            id_to_addresses.setdefault(coin_id, []).append(addr)
        if not id_to_addresses:
            return {}
        prices_by_id = self.get_prices(
            symbols=None,
            vs_currencies=vs_currencies,
            timeout=timeout,
            coin_ids=list(id_to_addresses.keys()),
        )
        result: dict[str, dict[str, Dezimal]] = {}
        for coin_id, addr_list in id_to_addresses.items():
            prices = prices_by_id.get(coin_id)
            if not prices:
                continue
            for addr in addr_list:
                result[addr] = dict(prices)
        return result

    def get_prices(
        self,
        symbols: list[str] | None,
        vs_currencies: list[str],
        timeout: int = TIMEOUT,
        coin_ids: list[str] | None = None,
    ) -> dict[str, dict[str, Dezimal]]:
        if coin_ids:
            deduped_ids, vs_param = self._validate_ids_and_prepare(
                coin_ids, vs_currencies
            )
            return self._aggregate_prices_by_ids(deduped_ids, vs_param, timeout)
        if not symbols:
            raise MissingFieldsError(["symbols"])
        return self._get_prices_impl(symbols, vs_currencies, timeout)

    def _get_prices_impl(
        self, symbols: list[str], vs_currencies: list[str], timeout: int
    ) -> dict[str, dict[str, Dezimal]]:
        deduped, vs_param = self._validate_and_prepare(symbols, vs_currencies)
        return self._aggregate_prices(deduped, vs_param, timeout)

    def _validate_and_prepare(
        self, symbols: list[str], vs_currencies: list[str]
    ) -> tuple[list[str], str]:
        if not symbols:
            raise MissingFieldsError(["symbols"])
        if not vs_currencies:
            raise MissingFieldsError(["vs_currencies"])
        deduped = self._dedupe_items(symbols, case_insensitive=True)
        vs_param = ",".join(c.lower() for c in vs_currencies)
        return deduped, vs_param

    def _aggregate_prices(
        self, deduped: list[str], vs_param: str, timeout: int
    ) -> dict[str, dict[str, Dezimal]]:
        result: dict[str, dict[str, Dezimal]] = {}
        for chunk in self._chunked(deduped, self.CHUNK_SIZE):
            chunk_result = self._fetch_chunk(chunk, vs_param, timeout)
            self._merge_prices_map(
                chunk_result, result, key_transform=lambda k: k.upper()
            )
        return result

    def _validate_ids_and_prepare(
        self, coin_ids: list[str], vs_currencies: list[str]
    ) -> tuple[list[str], str]:
        if not coin_ids:
            raise MissingFieldsError(["ids"])
        if not vs_currencies:
            raise MissingFieldsError(["vs_currencies"])
        deduped = self._dedupe_items(coin_ids, case_insensitive=True)
        vs_param = ",".join(c.lower() for c in vs_currencies)
        return deduped, vs_param

    def _aggregate_prices_by_ids(
        self, deduped: list[str], vs_param: str, timeout: int
    ) -> dict[str, dict[str, Dezimal]]:
        result: dict[str, dict[str, Dezimal]] = {}
        for chunk in self._chunked(deduped, self.CHUNK_SIZE):
            chunk_result = self._fetch_ids_chunk(chunk, vs_param, timeout)
            self._merge_prices_map(chunk_result, result, key_transform=lambda k: k)
        return result

    def _chunked(self, seq: list[str], size: int) -> list[list[str]]:
        return [seq[i : i + size] for i in range(0, len(seq), size)]

    def _merge_prices_map(
        self,
        raw_map: dict[str, Any],
        accumulator: dict[str, dict[str, Dezimal]],
        key_transform: Callable[[str], str],
    ) -> None:
        for key, prices in raw_map.items():
            converted = self._convert_prices(prices)
            if converted:
                accumulator[key_transform(key)] = converted

    def _convert_prices(self, prices: Any) -> dict[str, Dezimal]:
        if not isinstance(prices, dict):
            return {}
        converted: dict[str, Dezimal] = {}
        for cur, val in prices.items():
            try:
                converted[cur.upper()] = Dezimal(val)
            except Exception:
                continue
        return converted

    def _dedupe_items(self, items: list[str], case_insensitive: bool) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for raw in items:
            item = raw.strip()
            if not item:
                continue
            key = item.lower() if case_insensitive else item
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _fetch_chunk(
        self, chunk: list[str], vs_param: str, timeout: int
    ) -> dict[str, Any]:
        return self._fetch_simple_price(
            [s.lower() for s in chunk], vs_param, timeout, "symbols"
        )

    def _fetch_ids_chunk(
        self, chunk: list[str], vs_param: str, timeout: int
    ) -> dict[str, Any]:
        return self._fetch_simple_price(
            [c.lower() for c in chunk], vs_param, timeout, "ids"
        )

    def _fetch_simple_price(
        self,
        values: list[str],
        vs_param: str,
        timeout: int,
        identifier_key: str,
    ) -> dict[str, Any]:
        return self._fetch(
            "/simple/price",
            params={
                "vs_currencies": vs_param,
                identifier_key: ",".join(values),
                "precision": "full",
            },
            timeout=timeout,
        )

    # --- Token (contract) prices helpers ---
    def _fetch_token_chunk(
        self, chain_slug: str, chunk: list[str], vs_param: str, timeout: int
    ) -> dict[str, Any]:
        addresses_param = ",".join(chunk)
        path = f"/simple/token_price/{chain_slug}"
        return self._fetch(
            path,
            params={
                "vs_currencies": vs_param,
                "contract_addresses": addresses_param,
                "precision": "full",
            },
            timeout=timeout,
        )

    def _fetch(
        self, path: str, params: dict[str, Any] | None = None, timeout: int = TIMEOUT
    ) -> dict:
        url = f"{self.BASE_URL}{path}"
        try:
            response = http_get_with_backoff(
                url,
                params=params,
                timeout=timeout,
                max_retries=self.MAX_RETRIES,
                backoff_exponent_base=self.BACKOFF_EXPONENT_BASE,
                backoff_factor=self.BACKOFF_FACTOR,
                cooldown=self.COOLDOWN,
                log=self._log,
            )
        except requests.Timeout as e:
            self._log.warning(f"Timeout calling CoinGecko endpoint {url}")
            raise e
        except requests.RequestException as e:
            self._log.error(f"Request error calling CoinGecko endpoint {url}: {e}")
            raise e

        if not response.ok:
            status = response.status_code
            body = response.text
            if status == 429:
                raise TooManyRequests()
            if status in (401, 403):
                raise InvalidProvidedCredentials()
            if status == 400:
                self._log.error(f"Bad request to CoinGecko {url}: {body}")
                raise ValueError("Invalid request to CoinGecko API")
            if status in (500, 503):
                self._log.error(f"CoinGecko service error {status}: {body}")
                response.raise_for_status()
            if status == 408:
                self._log.warning(f"CoinGecko timeout status for {url}: {body}")
                response.raise_for_status()
            self._log.error(f"Unexpected CoinGecko response {status} for {url}: {body}")
            response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            self._log.error(
                f"Failed to decode JSON from CoinGecko for {url}: {response.text[:200]}"
            )
            raise
